# Standard libs
import httplib2
import json
import os
import datetime
from webapp2_extras import sessions
from webapp2_extras import i18n
import webapp2
import datetime
import time
import re
import jinja2

# Google libs
import endpoints
from google.appengine.ext import ndb
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from apiclient import errors
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

# Our libraries
from iomodels.crmengine.shows import Show
from endpoints_helper import EndpointsHelper
import model
from iomodels.crmengine.contacts import Contact
from iomodels.crmengine.leads import LeadInsertRequest,Lead
from iomodels.crmengine.documents import Document
import iomessages
from blog import Article
import iograph

# import event . hadji hicham 09-07-2014
from iomodels.crmengine.events import Event
# under the test .beata !

jinja_environment = jinja2.Environment(
  loader=jinja2.FileSystemLoader(os.getcwd()),
  extensions=['jinja2.ext.i18n'],cache_size=0)


jinja_environment.install_gettext_translations(i18n)
ADMIN_EMAILS = ['tedj.meabiou@gmail.com','hakim@iogrow.com']
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

SCOPES = [
    'https://www.googleapis.com/auth/plus.login https://www.googleapis.com/auth/prediction https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/calendar'
]

VISIBLE_ACTIONS = [
    'http://schemas.google.com/AddActivity',
    'http://schemas.google.com/ReviewActivity'
]

TOKEN_INFO_ENDPOINT = ('https://www.googleapis.com/oauth2/v1/tokeninfo' +
    '?access_token=%s')
TOKEN_REVOKE_ENDPOINT = 'https://accounts.google.com/o/oauth2/revoke?token=%s'

FOLDERS_ATTR = {
            'Account': 'accounts_folder',
            'Contact': 'contacts_folder',
            'Lead': 'leads_folder',
            'Opportunity': 'opportunities_folder',
            'Case': 'cases_folder',
            'Show': 'shows_folder',
            'Feedback': 'feedbacks_folder'
        }
FOLDERS = {
            'Accounts': 'accounts_folder',
            'Contacts': 'contacts_folder',
            'Leads': 'leads_folder',
            'Opportunities': 'opportunities_folder',
            'Cases': 'cases_folder'
        }
folders = {}

class BaseHandler(webapp2.RequestHandler):
    def set_user_locale(self,language=None):
        if language:
            locale = self.request.GET.get('locale', 'en_US')
            i18n.get_i18n().set_locale(language)

        else:
            locale = self.request.GET.get('locale', 'en_US')
            i18n.get_i18n().set_locale('en')

    def prepare_template(self,template_name):
        is_admin = False
        template_values={
                  'is_admin':is_admin
                  }
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            if user is not None:
                if user.email in ADMIN_EMAILS:
                    is_admin = True
                # Set the user locale from user's settings
                self.set_user_locale(user.language)
                tabs = user.get_user_active_tabs()

                # Set the user locale from user's settings
                self.set_user_locale(user.language)
                # Render the template
                active_app = user.get_user_active_app()
                apps = user.get_user_apps()
                is_business_user = bool(user.type=='business_user')
                applications = []
                for app in apps:
                    if app is not None:
                        applications.append(app)
                template_values={
                          'is_admin':is_admin,
                          'is_business_user':is_business_user,
                          'ME':user.google_user_id,
                          'active_app':active_app,
                          'apps':applications,
                          'tabs':tabs
                          }
        template = jinja_environment.get_template(template_name)
        self.response.out.write(template.render(template_values))

class SessionEnabledHandler(webapp2.RequestHandler):
    """Base type which ensures that derived types always have an HTTP session."""
    CURRENT_USER_SESSION_KEY = 'me'

    def dispatch(self):
        """Intercepts default request dispatching to ensure that an HTTP session
        has been created before calling dispatch in the base type.
        """
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)
        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        """Returns a session using the default cookie key."""
        return self.session_store.get_session()

    def get_user_from_session(self):
        """Convenience method for retrieving the users crendentials from an
        authenticated session.
        """
        email = self.session.get(self.CURRENT_USER_SESSION_KEY)
        if email is None:
          raise UserNotAuthorizedException('Session did not contain user email.')
        user = model.User.get_by_email(email)
        return user

class UserNotAuthorizedException(Exception):
    msg = 'Unauthorized request.'

class NotFoundException(Exception):
    msg = 'Resource not found.'

class RevokeException(Exception):
    msg = 'Failed to revoke token for given user.'

class WelcomeHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        template_values = {}
        template = jinja_environment.get_template('templates/live/welcome.html')
        self.response.out.write(template.render(template_values))


class IndexHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        # Check if the user is loged-in, if not redirect him to the sign-in page
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            try:
                user = self.get_user_from_session()
                if user.google_credentials is None:
                    self.redirect('/sign-in')
                logout_url = 'https://www.google.com/accounts/Logout?continue=https://appengine.google.com/_ah/logout?continue=http://www.iogrow.com/welcome/'
                if user is None or user.type=='public_user':
                    self.redirect('/welcome/')
                    return
                # Set the user locale from user's settings
                self.set_user_locale(user.language)
                uSerid = user.key.id()
                uSerlanguage = user.language
                apps = user.get_user_apps()
                admin_app = None
                active_app = user.get_user_active_app()
                tabs = user.get_user_active_tabs()
                applications = []
                for app in apps:
                    if app is not None:
                        applications.append(app)
                        if app.name=='admin':
                            admin_app = app

                template_values = {
                                  'tabs':tabs,
                                  'user':user,
                                  'logout_url' : logout_url,
                                  'CLIENT_ID': CLIENT_ID,
                                  'active_app':active_app,
                                  'apps': applications,
                                  'uSerid':uSerid,
                                  'uSerlanguage':uSerlanguage
                                }
                if admin_app:
                    template_values['admin_app']=admin_app
                template = jinja_environment.get_template('templates/base.html')
                self.response.out.write(template.render(template_values))
            except UserNotAuthorizedException as e:
                self.redirect('/welcome/')
        else:
            self.redirect('/welcome/')
class BlogHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        template_values = {}
        template = jinja_environment.get_template('templates/blog/blog_base.html')
        self.response.out.write(template.render(template_values))
class PublicArticlePageHandler(BaseHandler,SessionEnabledHandler):
    def get(self,id):
        article = Article.get_schema(id=id)
        template_values = {'article':article}
        template = jinja_environment.get_template('templates/blog/public_article_show.html')
        self.response.out.write(template.render(template_values))

class PublicSupport(BaseHandler,SessionEnabledHandler):
    def get(self):
        template_values = {}
        template = jinja_environment.get_template('templates/blog/public_support.html')
        self.response.out.write(template.render(template_values))
# Change the current app for example from sales to customer support
class ChangeActiveAppHandler(SessionEnabledHandler):
    def get(self,appid):
        new_app_id = int(appid)
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # get the active application before the change request
            active_app = user.get_user_active_app()
            new_active_app = model.Application.get_by_id(new_app_id)
            if new_active_app:
              if new_active_app.organization==user.organization:
                  user.set_user_active_app(new_active_app.key)
                  self.redirect(new_active_app.url)
              else:
                  self.redirect('/error')
            else:
                self.redirect('/')
        else:
            self.redirect('/sign-in')
class SignInHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        # Set the user locale from user's settings
        user_id = self.request.get('id')
        lang = self.request.get('language')
        self.set_user_locale(lang)
            # Render the template
        template_values = {
                            'CLIENT_ID': CLIENT_ID,
                            'ID' : user_id
                          }
        template = jinja_environment.get_template('templates/sign-in.html')
        self.response.out.write(template.render(template_values))

class EarlyBirdHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        # Set the user locale from user's settings
        user_id = self.request.get('id')
        lang = self.request.get('language')
        self.set_user_locale(lang)
            # Render the template
        template_values = {
                            'CLIENT_ID': CLIENT_ID,
                            'ID' : user_id
                          }
        template = jinja_environment.get_template('templates/early-bird.html')
        self.response.out.write(template.render(template_values))

class SignUpHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            template_values = {
              'userinfo': user,
              'CLIENT_ID': CLIENT_ID}
            template = jinja_environment.get_template('templates/sign-up.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect('/sign-in')
    @ndb.toplevel
    def post(self):
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            org_name = self.request.get('org_name')
            mob_phone = self.request.get('mob_phone')
            model.Organization.create_instance(org_name,user)
            self.redirect('/')
        else:
            self.redirect('/sign-in')

class StartEarlyBird(BaseHandler, SessionEnabledHandler):
    def get(self):
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            template_values = {
              'userinfo': user,
              'CLIENT_ID': CLIENT_ID}
            template = jinja_environment.get_template('templates/sign-up-early-bird.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect('/early-bird')
    @ndb.toplevel
    def post(self):
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            org_name = self.request.get('org_name')
            model.Organization.create_early_bird_instance(org_name,user)
            taskqueue.add(
                            url='/workers/add_to_iogrow_leads',
                            params={
                                    'email': user.email,
                                    'organization': org_name
                                    }
                        )
            self.redirect('/')
        else:
            self.redirect('/early-bird')

class GooglePlusConnect(SessionEnabledHandler):
    @staticmethod
    def exchange_code(code):
        """Exchanges the `code` member of the given AccessToken object, and returns
        the relevant credentials.

        Args:
          code: authorization code to exchange.

        Returns:
          Credentials response from Google indicating token information.

        Raises:
          FlowExchangeException Failed to exchange code (code invalid).
        """
        oauth_flow = flow_from_clientsecrets(
                                            'client_secrets.json',
                                            scope=SCOPES
                                          )
        oauth_flow.request_visible_actions = ' '.join(VISIBLE_ACTIONS)
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
        return credentials
    @staticmethod
    def get_token_info(credentials):
        """Get the token information from Google for the given credentials."""
        url = (TOKEN_INFO_ENDPOINT
               % credentials.access_token)
        return urlfetch.fetch(url)

    @staticmethod
    def get_user_profile(credentials):
        """Return the public Google+ profile data for the given user."""
        http = credentials.authorize(httplib2.Http(memcache))
        plus = build('plus', 'v1', http=http)
        return plus.people().get(userId='me').execute()
    @staticmethod
    def get_user_email(credentials):
        """Return the public Google+ profile data for the given user."""
        http = credentials.authorize(httplib2.Http(memcache))
        userinfo = build('oauth2', 'v1', http=http)
        return userinfo.userinfo().get().execute()

    @staticmethod
    def save_token_for_user(email, credentials,user_id=None):
        """Creates a user for the given ID and credential or updates the existing
        user with the existing credential.

        Args:
          google_user_id: Google user ID to update.
          credentials: Credential to set for the user.

        Returns:
          Updated User.
        """
        if user_id:
            user = model.User.get_by_id(user_id)
            userinfo = GooglePlusConnect.get_user_email(credentials)
            user.status = 'active'
            user.google_user_id = userinfo.get('id')
            user.google_display_name = userinfo.get('name')
            user.google_public_profile_url = userinfo.get('link')
            user.email = userinfo.get('email')
            user.google_public_profile_photo_url = userinfo.get('picture')
            invited_by = user.invited_by.get()
            user.organization = invited_by.organization
            profile =  model.Profile.query(
                                            model.Profile.name=='Standard User',
                                            model.Profile.organization==invited_by.organization
                                          ).get()
            model.Invitation.delete_by(user.email)
            user.init_user_config(invited_by.organization,profile.key)
        else:
            user = model.User.get_by_email(email)
        if user is None:
            userinfo = GooglePlusConnect.get_user_email(credentials)
            user = model.User()
            user.type = 'public_user'
            user.status = 'active'
            user.google_user_id = userinfo.get('id')
            user.google_display_name = userinfo.get('name')
            user.google_public_profile_url = userinfo.get('link')
            user.email = userinfo.get('email')
            user.google_public_profile_photo_url = userinfo.get('picture')
        user.google_credentials = credentials
        user_key = user.put_async()
        user_key_async = user_key.get_result()
        if memcache.get(user.email) :
            memcache.set(user.email, user)
        else:
            memcache.add(user.email, user)
        if not user.google_contacts_group:
            taskqueue.add(
                            url='/workers/createcontactsgroup',
                            params={
                                    'email': user.email
                                    }
                        )
        return user

    def post(self):
        #try to get the user credentials from the code
        credentials = None
        code = self.request.get("code")
        try:
            credentials = GooglePlusConnect.exchange_code(code)
        except FlowExchangeError:
            return
        token_info = GooglePlusConnect.get_token_info(credentials)
        if token_info.status_code != 200:
            return
        token_info = json.loads(token_info.content)
        # If there was an error in the token info, abort.
        if token_info.get('error') is not None:
            return
        # Make sure the token we got is for our app.
        expr = re.compile("(\d*)(.*).apps.googleusercontent.com")
        issued_to_match = expr.match(token_info.get('issued_to'))
        local_id_match = expr.match(CLIENT_ID)
        if (not issued_to_match
            or not local_id_match
            or issued_to_match.group(1) != local_id_match.group(1)):
            return
        #Check if is it an invitation to sign-in or just a simple sign-in
        invited_user_id = None
        invited_user_id_request = self.request.get("id")
        if invited_user_id_request:
            invited_user_id = long(invited_user_id_request)
        #user = model.User.query(model.User.google_user_id == token_info.get('user_id')).get()

        # Store our credentials with in the datastore with our user.
        if invited_user_id:
            user = GooglePlusConnect.save_token_for_user(
                                                        token_info.get('email'),
                                                        credentials,
                                                        invited_user_id
                                                      )
        else:
            user = GooglePlusConnect.save_token_for_user(
                                                        token_info.get('email'),
                                                        credentials
                                                      )
        # if user doesn't have organization redirect him to sign-up
        isNewUser = False
        if user.organization is None:
            isNewUser = True
        # Store the user ID in the session for later use.
        self.session[self.CURRENT_USER_SESSION_KEY] = user.email
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(isNewUser))

class ArticleSearchHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/articles/article_search.html')

class ArticleListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/articles/article_list.html')

class ArticleShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/articles/article_show.html')
class ArticleNewHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/articles/article_new.html')

class AccountListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/accounts/account_list.html')

class AccountShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/accounts/account_show.html')

class AccountNewHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/accounts/account_new.html')

class ContactListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/contacts/contact_list.html')

class ContactShowHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/contacts/contact_show.html')

class ContactNewHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/contacts/contact_new.html')

class OpportunityListHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/opportunities/opportunity_list.html')

class OpportunityShowHandler(BaseHandler,SessionEnabledHandler):
    def get (self):
        self.prepare_template('templates/opportunities/opportunity_show.html')

class OpportunityNewHandler(BaseHandler,SessionEnabledHandler):
    def get (self):
        self.prepare_template('templates/opportunities/opportunity_new.html')

class LeadListHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/leads/lead_list.html')

class LeadShowHandler(BaseHandler,SessionEnabledHandler):
    def get (self):
        self.prepare_template('templates/leads/lead_show.html')

class LeadNewHandler(BaseHandler,SessionEnabledHandler):
    def get (self):
        self.prepare_template('templates/leads/lead_new.html')

class CaseNewHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/cases/case_new.html')

class CaseListHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/cases/case_list.html')

class CaseShowHandler(BaseHandler,SessionEnabledHandler):
    def get (self):
        self.prepare_template('templates/cases/case_show.html')

class NeedShowHandler(BaseHandler,SessionEnabledHandler):
    def get (self):
        self.prepare_template('templates/needs/show.html')

class NoteShowHandler (BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/accounts/note_show.html')

class DocumentShowHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/documents/show.html')

class AllTasksHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/activities/all_tasks.html')

class TaskShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/activities/task_show.html')

class EventShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/activities/event_show.html')

class ShowListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/live/shows/list_show.html')

class ShowShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/live/shows/show.html')

class UserListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/admin/users/list.html')

class GroupListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/admin/groups/list.html')

class GroupShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/admin/groups/show.html')

class settingsShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/admin/settings/settings.html')

class SearchListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/search/list.html')
class CalendarShowHandler(BaseHandler,SessionEnabledHandler):
    def get(self):
        self.prepare_template('templates/calendar/calendar_show.html')
# Workers
class CreateOrganizationFolders(webapp2.RequestHandler):
    @staticmethod
    def init_drive_folder(http,driveservice,folder_name,parent=None):
        folder = {
                'title': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent:
            folder['parents'] = [{'id': parent}]
        try:
            created_folder = driveservice.files().insert(fields='id',body=folder).execute()
            return created_folder['id']
        except errors.HttpError, error:
            print 'An error occured: %s' % error
            return None

    @staticmethod
    def folder_created_callback(request_id, response, exception):
        global folders
        if exception is not None:
            # Do something with the exception
            pass
        else:
            # Do something with the response
            folder_name = response['title']
            folders[folder_name] = response['id']

    def post(self): # should run at most 1/s due to entity group limit
        admin = model.User.get_by_email(self.request.get('email'))
        credentials = admin.google_credentials
        org_key_str = self.request.get('org_key')
        org_key = ndb.Key(urlsafe=org_key_str)
        organization = org_key.get()
        http = credentials.authorize(httplib2.Http(memcache))
        driveservice = build('drive', 'v2', http=http)
        # init the root folder
        org_folder = self.init_drive_folder(http,driveservice,organization.name+' (ioGrow)')
        # init objects folders
        batch = BatchHttpRequest()
        for folder_name in FOLDERS.keys():
            folder = {
                    'title': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents' : [{'id': org_folder}]
            }
            batch.add(driveservice.files().insert(
                                                fields='id,title',
                                                body=folder),
                                                callback=self.folder_created_callback
                                                )
        batch.execute(http=http)
        organization.org_folder = org_folder
        for folder_name in FOLDERS.keys():
            if folder_name in folders.keys():
                setattr(organization, FOLDERS[folder_name], folders[folder_name])
        organization.put()

class CreateContactsGroup(webapp2.RequestHandler):
    @ndb.toplevel
    def post(self):
        email = self.request.get('email')
        user = model.User.get_by_email(email)
        contacts_group_id = EndpointsHelper.create_contact_group(user.google_credentials)
        user.google_contacts_group = contacts_group_id
        user.put_async()
        model.User.memcache_update(user,email)

class SyncContact(webapp2.RequestHandler):
    @ndb.toplevel
    def post(self):
        # get request params
        email = self.request.get('email')
        id = self.request.get('id')
        user = model.User.get_by_email(email)

        # sync contact
        Contact.sync_with_google_contacts(user,id)

class CreateObjectFolder(webapp2.RequestHandler):
    @staticmethod
    def insert_folder(user, folder_name, kind,logo_img_id=None):
        try:
            credentials = user.google_credentials
            http = credentials.authorize(httplib2.Http(memcache))
            service = build('drive', 'v2', http=http)
            organization = user.organization.get()

            # prepare params to insert
            folder_params = {
                        'title': folder_name,
                        'mimeType':  'application/vnd.google-apps.folder'
            }#get the accounts_folder or contacts_folder or ..
            parent_folder = eval('organization.'+FOLDERS_ATTR[kind])
            if parent_folder:
                folder_params['parents'] = [{'id': parent_folder}]

            created_folder = service.files().insert(body=folder_params,fields='id').execute()
            # move the image to the created folder
            if logo_img_id:
                params = {
                      'parents': [{'id': created_folder['id']}]
                    }
                service.files().patch(
                                    fileId=logo_img_id,
                                    body=params,
                                    fields='id').execute()
        except:
            raise endpoints.UnauthorizedException(EndpointsHelper.INVALID_GRANT)

        return created_folder
    @ndb.toplevel
    def post(self):
        folder_name = self.request.get('folder_name')
        kind = self.request.get('kind')
        user = model.User.get_by_email(self.request.get('email'))
        logo_img_id = self.request.get('logo_img_id')
        if logo_img_id == 'None':
            logo_img_id = None
        created_folder = self.insert_folder(user,folder_name,kind,logo_img_id)
        object_key_str = self.request.get('obj_key')
        object_key = ndb.Key(urlsafe=object_key_str)
        obj = object_key.get()
        obj.folder = created_folder['id']
        obj.put_async()

class SyncCalendarEvent(webapp2.RequestHandler):
    def post(self):
        user_from_email = model.User.get_by_email(self.request.get('email'))
        starts_at = datetime.datetime.strptime(
                                              self.request.get('starts_at'),
                                              "%Y-%m-%dT%H:%M:00.000000"
                                              )
        summary = self.request.get('summary')
        location = self.request.get('location')
        ends_at = datetime.datetime.strptime(
                                              self.request.get('ends_at'),
                                              "%Y-%m-%dT%H:%M:00.000000"
                                              )
        event=Event.getEventById(self.request.get('event_id'))
        try:
            credentials = user_from_email.google_credentials
            http = credentials.authorize(httplib2.Http(memcache))
            service = build('calendar', 'v3', http=http)
            # prepare params to insert
            params = {
                 "start":
                  {
                    "dateTime": starts_at.strftime("%Y-%m-%dT%H:%M:00.000+01:00")
                  },
                 "end":
                  {
                    "dateTime": ends_at.strftime("%Y-%m-%dT%H:%M:00.000+01:00")
                  },
                  "summary": summary
            }

            created_event = service.events().insert(calendarId='primary',body=params).execute()
            event.event_google_id=created_event['id']
            event.put()
        except:
            raise endpoints.UnauthorizedException('Invalid grant' )


# syncronize tasks with google calendar . hadji hicham 10-07-2014.
class SyncCalendarTask(webapp2.RequestHandler):
    def post(self):
        user_from_email = model.User.get_by_email(self.request.get('email'))
        starts_at = datetime.datetime.strptime(
                                              self.request.get('starts_at'),
                                              "%Y-%m-%dT%H:%M:00.000000"
                                              )
        summary = self.request.get('summary')
        location = self.request.get('location')
        ends_at = datetime.datetime.strptime(
                                              self.request.get('ends_at'),
                                              "%Y-%m-%dT%H:%M:00.000000"
                                              )
        task=Task.getTaskById(self.request.get('task_id'))
        credentials = user_from_email.google_credentials
        http = credentials.authorize(httplib2.Http(memcache))
        service = build('calendar', 'v3', http=http)
            # prepare params to insert
        params = {
                 "start":
                  {
                    "date": starts_at.strftime("%Y-%m-%d")
                  },
                 "end":
                  {
                    "date": ends_at.strftime("%Y-%m-%d")
                  },
                  "summary": summary,
            }

        created_task = service.events().insert(calendarId='primary',body=params).execute()
        task.task_google_id=created_task['id']
        task.put()


class SyncPatchCalendarEvent(webapp2.RequestHandler):
    def post(self):
        user_from_email = model.User.get_by_email(self.request.get('email'))
        starts_at = datetime.datetime.strptime(
                                              self.request.get('starts_at'),
                                              "%Y-%m-%dT%H:%M:00.000000"
                                              )
        summary = self.request.get('summary')
        location = self.request.get('location')
        ends_at = datetime.datetime.strptime(
                                              self.request.get('ends_at'),
                                              "%Y-%m-%dT%H:%M:00.000000"
                                              )
        event_google_id= self.request.get('event_google_id')
        try:
            credentials = user_from_email.google_credentials
            http = credentials.authorize(httplib2.Http(memcache))
            service = build('calendar', 'v3', http=http)
            # prepare params to insert
            params = {
                 "start":
                  {
                    "dateTime": starts_at.strftime("%Y-%m-%dT%H:%M:00.000+01:00")
                  },
                 "end":
                  {
                    "dateTime": ends_at.strftime("%Y-%m-%dT%H:%M:00.000+01:00")
                  },
                  "summary": summary
                  }


            patched_event = service.events().patch(calendarId='primary',eventId=event_google_id,body=params).execute()
        except:
            raise endpoints.UnauthorizedException('Invalid grant' )

# syncronize tasks with google calendar . hadji hicham 10-07-2014.
class SyncPatchCalendarTask(webapp2.RequestHandler):
    def post(self):
        user_from_email = model.User.get_by_email(self.request.get('email'))
        starts_at = datetime.datetime.strptime(
                                              self.request.get('starts_at'),
                                              "%Y-%m-%dT%H:%M:00.000000"
                                              )
        summary = self.request.get('summary')
        location = self.request.get('location')
        ends_at = datetime.datetime.strptime(
                                              self.request.get('ends_at'),
                                              "%Y-%m-%dT%H:%M:00.000000"
                                              )
        task_google_id= self.request.get('task_google_id')
        try:
            credentials = user_from_email.google_credentials
            http = credentials.authorize(httplib2.Http(memcache))
            service = build('calendar', 'v3', http=http)
            # prepare params to insert
            params = {
                 "start":
                  {
                    "date": starts_at.strftime("%Y-%m-%d")
                  },
                 "end":
                  {
                    "date": ends_at.strftime("%Y-%m-%d")
                  },
                  "summary": summary
                  }


            patched_event = service.events().patch(calendarId='primary',eventId=task_google_id,body=params).execute()
        except:
            raise endpoints.UnauthorizedException('Invalid grant' )

# sync delete events with google calendar . hadjo hicham 09-08-2014
class SyncDeleteCalendarEvent(webapp2.RequestHandler):
    def post(self):
        user_from_email = model.User.get_by_email(self.request.get('email'))
        event_google_id= self.request.get('event_google_id')
        try:
            credentials = user_from_email.google_credentials
            http = credentials.authorize(httplib2.Http(memcache))
            service = build('calendar', 'v3', http=http)
            # prepare params to insert
            patched_event = service.events().delete(calendarId='primary',eventId=event_google_id).execute()
        except:
            raise endpoints.UnauthorizedException('Invalid grant' )

class AddToIoGrowLeads(webapp2.RequestHandler):
    def post(self):
        user_from_email = model.User.get_by_email('tedj.meabiou@gmail.com')
        lead = model.User.get_by_email(self.request.get('email'))
        company = self.request.get('organization')
        email = iomessages.EmailSchema(email=lead.email)
        emails = []
        emails.append(email)
        request = LeadInsertRequest(
                                    firstname = lead.google_display_name.split()[0],
                                    lastname = " ".join(lead.google_display_name.split()[1:]),
                                    emails = emails,
                                    profile_img_url = lead.google_public_profile_photo_url,
                                    company = company,
                                    access = 'public'
        )
        Lead.insert(user_from_email,request)

class ShareDocument(webapp2.RequestHandler):
    def post(self):
        email = self.request.get('email')
        doc_id = self.request.get('doc_id')
        resource_id = self.request.get('resource_id')
        user_email = self.request.get('user_email')
        access = self.request.get('access')
        if access=='anyone':
            # public
            owner = model.User.get_by_email(user_email)
            credentials = owner.google_credentials
            http = credentials.authorize(httplib2.Http(memcache))
            service = build('drive', 'v2', http=http)
            # prepare params to insert
            params = {
                      'role': 'reader',
                      'type': 'anyone'
                      }
            service.permissions().insert(
                                        fileId=resource_id,
                                        body=params,
                                        sendNotificationEmails=False,
                                        fields='id').execute()
        else:
            document = Document.get_by_id(int(doc_id))
            if document:

                    owner = model.User.get_by_gid(document.owner)
                    if owner.email != email:
                        credentials = owner.google_credentials
                        http = credentials.authorize(httplib2.Http(memcache))
                        service = build('drive', 'v2', http=http)
                        # prepare params to insert
                        params = {
                                      'role': 'writer',
                                      'type': 'user',
                                      'value':email
                                    }
                        service.permissions().insert(
                                                        fileId=document.resource_id,
                                                        body=params,
                                                        sendNotificationEmails=False,
                                                        fields='id').execute()


class InitPeerToPeerDrive(webapp2.RequestHandler):
    def post(self):
        invited_by_email = self.request.get('invited_by_email')
        email = self.request.get('email')
        user = model.User.get_by_email(email)
        invited_by = model.User.get_by_email(invited_by_email)
        documents = Document.query(
                                  Document.organization == invited_by.organization,
                                  Document.access=='public'
                                  ).fetch()
        for document in documents:
            taskqueue.add(
                            url='/workers/sharedocument',
                            params={
                                    'email': email,
                                    'doc_id': str(document.key.id())
                                    }
                        )
class ShareObjectDocuments(webapp2.RequestHandler):
    def post(self):
        obj_key_str = self.request.get('obj_key_str')
        parent_key = ndb.Key(urlsafe=obj_key_str)
        email = self.request.get('email')
        documents = Document.list_by_parent(parent_key)
        for document in documents.items:
            taskqueue.add(
                            url='/workers/sharedocument',
                            params={
                                    'email': email,
                                    'doc_id': document.id
                                    }
                        )
class SyncDocumentWithTeam(webapp2.RequestHandler):
    def post(self):
        user_email = self.request.get('user_email')
        doc_id = self.request.get('doc_id')
        parent_key_str = self.request.get('parent_key_str')
        parent_key = ndb.Key(urlsafe=parent_key_str)
        parent = parent_key.get()
        collaborators = []
        if parent.access == 'public':
            collaborators = model.User.query(model.User.organization==parent.organization)
        elif parent.access == 'private':
            # list collborators who have access
            acl = EndpointsHelper.who_has_access(parent_key)
            collaborators = acl['collaborators']
            if acl['owner'] is not None:
                collaborators.append(acl['owner'])
        for collaborator in collaborators:
            if collaborator.email != user_email :
                taskqueue.add(
                                url='/workers/sharedocument',
                                params={
                                        'email': collaborator.email,
                                        'doc_id': doc_id
                                        }
                            )








routes = [
    # Task Queues Handlers
    ('/workers/initpeertopeerdrive',InitPeerToPeerDrive),
    ('/workers/sharedocument',ShareDocument),
    ('/workers/shareobjectdocument',ShareObjectDocuments),
    ('/workers/syncdocumentwithteam',SyncDocumentWithTeam),
    ('/workers/createorgfolders',CreateOrganizationFolders),
    ('/workers/createobjectfolder',CreateObjectFolder),
    ('/workers/syncevent',SyncCalendarEvent),
    ('/workers/syncpatchevent',SyncPatchCalendarEvent),
    ('/workers/syncdeleteevent',SyncDeleteCalendarEvent),
    ('/workers/createcontactsgroup',CreateContactsGroup),
    ('/workers/sync_contacts',SyncContact),
    ('/workers/add_to_iogrow_leads',AddToIoGrowLeads),

    ('/',IndexHandler),
    ('/blog',BlogHandler),
    ('/support',PublicSupport),
    (r'/blog/articles/(\d+)', PublicArticlePageHandler),
    ('/views/articles/list',ArticleListHandler),
    ('/views/articles/show',ArticleShowHandler),
    ('/views/articles/new',ArticleNewHandler),
    ('/views/articles/search',ArticleSearchHandler),

    # Templates Views Routes
    # Accounts Views
    ('/views/accounts/list',AccountListHandler),
    ('/views/accounts/show',AccountShowHandler),
    ('/views/accounts/new',AccountNewHandler),
    # Contacts Views
    ('/views/contacts/list',ContactListHandler),
    ('/views/contacts/show',ContactShowHandler),
    ('/views/contacts/new',ContactNewHandler),
    # Shows Views
    ('/views/shows/list',ShowListHandler),
    ('/views/shows/show',ShowShowHandler),

    # Opportunities Views
    ('/views/opportunities/list',OpportunityListHandler),
    ('/views/opportunities/show',OpportunityShowHandler),
    ('/views/opportunities/new',OpportunityNewHandler),

    # Leads Views
    ('/views/leads/list',LeadListHandler),
    ('/views/leads/show',LeadShowHandler),
    ('/views/leads/new',LeadNewHandler),
    # Cases Views
    ('/views/cases/list',CaseListHandler),
    ('/views/cases/show',CaseShowHandler),
    ('/views/cases/new',CaseNewHandler),

    # Needs Views
    ('/views/needs/show',NeedShowHandler),

    # Notes, Documents, Taks, Events, Search Views
    ('/views/notes/show',NoteShowHandler),
    ('/views/documents/show',DocumentShowHandler),

    ('/views/search/list',SearchListHandler),
    ('/views/tasks/show',TaskShowHandler),
    ('/views/tasks/list',AllTasksHandler),
    ('/views/events/show',EventShowHandler),
     ('/views/calendar/show',CalendarShowHandler),
    # Admin Console Views
    ('/views/admin/users/list',UserListHandler),
    ('/views/admin/groups/list',GroupListHandler),
    ('/views/admin/groups/show',GroupShowHandler),
    ('/views/admin/settings',settingsShowHandler),
    # Applications settings
    (r'/apps/(\d+)', ChangeActiveAppHandler),
    # ioGrow Live
    ('/welcome/',WelcomeHandler),
    # Authentication Handlers
    ('/early-bird',EarlyBirdHandler),
    ('/start-early-bird-account',StartEarlyBird),
    ('/sign-in',SignInHandler),
    ('/sign-up',SignUpHandler),
    ('/gconnect',GooglePlusConnect)
    ]
config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'YOUR_SESSION_SECRET'
}
app = webapp2.WSGIApplication(routes, config=config, debug=True)
