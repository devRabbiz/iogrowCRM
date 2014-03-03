from google.appengine.ext import ndb
from endpoints_proto_datastore.ndb import EndpointsModel
from endpoints_proto_datastore import MessageFieldsSchema
from google.appengine.api import search
from protorpc import messages
import endpoints

from search_helper import tokenize_autocomplete 

import model
from iomodels.crmengine.tags import Tag,TagSchema
from iomodels.crmengine.contacts import Contact,ContactListResponse
from iograph import Node,Edge,InfoNodeListResponse
from iomodels.crmengine.notes import Note,TopicListResponse


# The message class that defines the EntityKey schema
class EntityKeyRequest(messages.Message):
    entityKey = messages.StringField(1)

 # The message class that defines the ListRequest schema
class ListRequest(messages.Message):
    limit = messages.IntegerField(1)
    pageToken = messages.StringField(2)

class AccountGetRequest(messages.Message):
    id = messages.IntegerField(1,required = True)
    contacts = messages.MessageField(ListRequest, 2)
    topics = messages.MessageField(ListRequest, 3)

class AccountSchema(messages.Message):
    id = messages.StringField(1)
    entityKey = messages.StringField(2)
    name = messages.StringField(3)
    account_type = messages.StringField(4)
    industry = messages.StringField(5)
    tagline = messages.StringField(6)
    introduction = messages.StringField(7)
    tags = messages.MessageField(TagSchema,8, repeated = True)
    contacts = messages.MessageField(ContactListResponse,9)
    infonodes = messages.MessageField(InfoNodeListResponse,10)
    topics = messages.MessageField(TopicListResponse,11)
    created_at = messages.StringField(12)
    updated_at = messages.StringField(13)
    access = messages.StringField(14)

class AccountListResponse(messages.Message):
    items = messages.MessageField(AccountSchema, 1, repeated=True)
    nextPageToken = messages.StringField(2)

class Account(EndpointsModel):
    _message_fields_schema = ('id','entityKey','created_at','updated_at', 'folder','access','collaborators_list','phones','emails','addresses','websites','sociallinks', 'collaborators_ids','name','owner','account_type','industry','tagline','introduction')
    # Sharing fields
    owner = ndb.StringProperty()
    collaborators_list = ndb.StructuredProperty(model.Userinfo,repeated=True)
    collaborators_ids = ndb.StringProperty(repeated=True)
    organization = ndb.KeyProperty()
    folder = ndb.StringProperty()
    name = ndb.StringProperty()
    account_type = ndb.StringProperty()
    industry = ndb.StringProperty()
    created_at = ndb.DateTimeProperty(auto_now_add=True)
    updated_at = ndb.DateTimeProperty(auto_now=True)
    tagline = ndb.TextProperty()
    introduction =ndb.TextProperty()
    # public or private
    access = ndb.StringProperty()
    phones = ndb.StructuredProperty(model.Phone,repeated=True)
    emails = ndb.StructuredProperty(model.Email,repeated=True)
    addresses = ndb.StructuredProperty(model.Address,repeated=True)
    websites = ndb.StructuredProperty(model.Website,repeated=True)
    sociallinks= ndb.StructuredProperty(model.Social,repeated=True)


    def put(self, **kwargs):
        ndb.Model.put(self, **kwargs)
        self.put_index()
        self.set_perm()

    def set_perm(self):
        about_item = str(self.key.id())

        perm = model.Permission(about_kind='Account',
                         about_item=about_item,
                         type = 'user',
                         role = 'owner',
                         value = self.owner)
        perm.put()

    def put_index(self,data=None):
        """ index the element at each"""
        empty_string = lambda x: x if x else ""
        collaborators = " ".join(self.collaborators_ids)
        organization = str(self.organization.id())
        emails = " ".join(map(lambda x: x.email,  self.emails))
        phones = " ".join(map(lambda x: x.number,  self.phones))
        websites =  " ".join(map(lambda x: x.website,  self.websites))
        title_autocomplete = ','.join(tokenize_autocomplete(self.name))
        
        #addresses = " \n".join(map(lambda x: " ".join([x.street,x.city,x.state, str(x.postal_code), x.country]) if x else "", self.addresses))
        if data:
            search_key = ['infos','tags']
            for key in search_key:
                if key not in data.keys():
                    data[key] = ""
            my_document = search.Document(
            doc_id = str(data['id']),
            fields=[
                search.TextField(name=u'type', value=u'Account'),
                search.TextField(name='organization', value = empty_string(organization) ),
                search.TextField(name='entityKey',value=empty_string(self.key.urlsafe())),
                search.TextField(name='access', value = empty_string(self.access) ),
                search.TextField(name='owner', value = empty_string(self.owner) ),
                search.TextField(name='collaborators', value = collaborators ),
                search.TextField(name='title', value = empty_string(self.name) ),
                search.TextField(name='account_type', value = empty_string(self.account_type)),
                search.TextField(name='industry', value = empty_string(self.industry)),
                search.DateField(name='created_at', value = self.created_at),
                search.DateField(name='updated_at', value = self.updated_at),
                search.TextField(name='industry', value = empty_string(self.industry)),
                search.TextField(name='tagline', value = empty_string(self.tagline)),
                search.TextField(name='introduction', value = empty_string(self.introduction)),
                search.TextField(name='emails', value = empty_string(emails)),
                search.TextField(name='phones', value = empty_string(phones)),
                search.TextField(name='websites', value = empty_string(websites)),
                search.TextField(name='infos', value= data['infos']),
                search.TextField(name='tags', value= data['tags']),
                search.TextField(name='title_autocomplete', value = empty_string(title_autocomplete)),
                #search.TextField(name='addresses', value = empty_string(addresses)),
               ])
        else:
            my_document = search.Document(
            doc_id = str(self.key.id()),
            fields=[
                search.TextField(name=u'type', value=u'Account'),
                search.TextField(name='organization', value = empty_string(organization) ),
                search.TextField(name='entityKey',value=empty_string(self.key.urlsafe())),
                search.TextField(name='access', value = empty_string(self.access) ),
                search.TextField(name='owner', value = empty_string(self.owner) ),
                search.TextField(name='collaborators', value = collaborators ),
                search.TextField(name='title', value = empty_string(self.name) ),
                search.TextField(name='account_type', value = empty_string(self.account_type)),
                search.TextField(name='industry', value = empty_string(self.industry)),
                search.DateField(name='created_at', value = self.created_at),
                search.DateField(name='updated_at', value = self.updated_at),
                search.TextField(name='industry', value = empty_string(self.industry)),
                search.TextField(name='tagline', value = empty_string(self.tagline)),
                search.TextField(name='introduction', value = empty_string(self.introduction)),
                search.TextField(name='emails', value = empty_string(emails)),
                search.TextField(name='phones', value = empty_string(phones)),
                search.TextField(name='websites', value = empty_string(websites)),
                search.TextField(name='title_autocomplete', value = empty_string(title_autocomplete)),
                #search.TextField(name='addresses', value = empty_string(addresses)),
               ])
        my_index = search.Index(name="GlobalIndex")
        my_index.put(my_document)

    @classmethod
    def get_schema(cls,request):
        account = Account.get_by_id(int(request.id))
        if account is None:
            raise endpoints.NotFoundException('Account not found.')
        #list of tags related to this account
        tag_list = Tag.list_by_parent(account.key)
        #list of contacts to this account
        contacts = None
        if request.contacts:
            contacts = Contact.list_by_parent(
                                            parent_key = account.key,
                                            request = request
                                        )
        #list of topics related to this account
        topics = None
        if request.topics:
            topics = Note.list_by_parent(
                                        parent_key = account.key,
                                        request = request
                                        )
        # list of infonodes
        infonodes = Node.list_info_nodes(
                                        parent_key = account.key,
                                        request = request
                                        )
        account_schema = AccountSchema(
                                  id = str( account.key.id() ),
                                  entityKey = account.key.urlsafe(),
                                  access = account.access,
                                  name = account.name,
                                  account_type = account.account_type,
                                  industry = account.industry,
                                  tagline = account.tagline,
                                  introduction = account.introduction,
                                  tags = tag_list,
                                  contacts = contacts,
                                  topics = topics,
                                  infonodes = infonodes,
                                  created_at = account.created_at.strftime("%Y-%m-%dT%H:%M:00.000"),
                                  updated_at = account.updated_at.strftime("%Y-%m-%dT%H:%M:00.000")
                                )

        return  account_schema








