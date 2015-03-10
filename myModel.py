from mapreduce import operation as op,context
from model import Tab
from model import Application
from google.appengine.ext import ndb

def is_admin(entity):
    """
    Update the entities timestamp.
    """
    organization=entity.organization.get()

    if organization.owner==entity.google_user_id:
       entity.is_admin=True
    yield op.db.Put(entity)
    yield op.counters.Increment('touched')
def delete_group_tab(entity):
    delete=False
    if entity.name=="admin":
       for x in xrange(1,len(entity.tabs)):
           tab=entity.tabs[x].get()
           if tab.name=="Groups":
              delete=True
    if delete:
       entity.tabs.pop(1)         
    yield op.db.Put(entity)
    yield op.counters.Increment('touched')

def touch(entity):
    yield op.db.Put(entity)
    yield op.counters.Increment('touched')

def add_dashboard_tab(entity):
    add_dashboard_tab=True
    if entity.name=="sales":
      for x in xrange(1,len(entity.tabs)):
           tab=entity.tabs[x].get()
           if tab.name=="Dashboard":
              add_dashboard_tab=False
      if add_dashboard_tab:
        org_key=entity.organization
        created_tab=Tab(name='Dashboard',label='Dashboard',url='/#/dashboard/',icon='dashboard',organization=org_key)
        tab_key=created_tab.put()
        entity.tabs.append(tab_key)
    yield op.db.Put(entity)
    yield op.counters.Increment('touched')

def delete_tab_group_from_datastore(entity):
      if entity.name=="Groups":
        yield op.db.Delete(entity)
        yield op.counters.Increment('touched')

def delete_iogrow_groups_tab(entity):
    params = context.get().mapreduce_spec.mapper.params
    iogrow_organization_key=params.get('organization_key')
    if entity.name=="admin":
       if iogrow_organization_key==entity.organization.urlsafe():
          entity.tabs.pop(1) 
    yield op.db.Put(entity)
    yield op.counters.Increment('touched')
   
def add_discovery_tab(entity):
    add_discovery_tab=True
    if entity.name=="sales":
      for x in xrange(1,len(entity.tabs)):
           tab=entity.tabs[x].get()
           if tab.name=="Discovery":
              add_discovery_tab=False
      if add_discovery_tab:
         org_key=entity.organization
         created_tab=Tab(name='Discovery',label='Discovery',url='/#/discovers/',icon='twitter',organization=org_key)
         tab_key=created_tab.put()
         entity.tabs.insert(0,tab_key)
         print "-------------yalla asia-----------"
         print entity.tabs
         print "---------------------------------"
    yield op.db.Put(entity)
    yield op.counters.Increment('touched')

def upgrade_early_birds(entity):
    new_tabs=[
                {'name': 'Discovery','label': 'Discovery','url':'/#/discovers/','icon':'twitter'},
                {'name': 'Leads','label': 'Leads','url':'/#/leads/','icon':'road'},
                {'name': 'Opportunities','label': 'Opportunities','url':'/#/opportunities/','icon':'money'},
                {'name': 'Contacts','label': 'Contacts','url':'/#/contacts/','icon':'group'},
                {'name': 'Accounts','label': 'Accounts','url':'/#/accounts/','icon':'building'},
                {'name': 'Cases','label': 'Cases','url':'/#/cases/','icon':'suitcase'},
                {'name': 'Tasks','label': 'Tasks','url':'/#/tasks/','icon':'check'},
                {'name': 'Calendar','label': 'Calendar','url':'/#/calendar/','icon':'calendar'},
                {'name': 'Dashboard','label': 'Dashboard','url':'/#/dashboard/','icon':'dashboard'}
              ]
    if entity.type=="early_bird":
       application=entity.active_app.get()
       org_key=entity.organization
       if application.label=="Relationships":
          application.tabs=[]
          application.put()
          created_tabs=[]
          for tab in new_tabs:
            created_tab = Tab(name=tab['name'],label=tab['label'],url=tab['url'],icon=tab['icon'],organization=org_key)
            tab_key = created_tab.put()
            created_tabs.append(tab_key)
          application.tabs=created_tabs
          application.put()

    yield op.db.Put(entity)
    yield op.counters.Increment('touched')

def sort_tabs(entity):
    if entity.label =="Relationships":
       ordered_list=[]
       ordered_list.append(entity.tabs[0])
       ordered_list.append(entity.tabs[4])
       ordered_list.append(entity.tabs[3])
       ordered_list.append(entity.tabs[2])
       ordered_list.append(entity.tabs[1])
       ordered_list.append(entity.tabs[5])
       ordered_list.append(entity.tabs[6])
       ordered_list.append(entity.tabs[7])
       ordered_list.append(entity.tabs[8]) 
       entity.tabs=ordered_list 

    yield op.db.Put(entity)
    yield op.counters.Increment('touched')


def change_account_icon(entity):
    if entity.label=="Accounts":
       entity.icon="building"
    yield op.db.Put(entity)
    yield op.counters.Increment('touched')

def delete_unused_tabs(entity):
    Applications=Application.query().filter(Application.organization==entity.key)
    existed_tabs=Tab.query().filter(Tab.organization==entity.key).fetch()
    try:
      for app in Applications:
          if app.label=="Relationships":
             used_io_tabs=app.tabs
          elif app.label =="Admin Console":
             used_admin_tabs=app.tabs
    except:
      pass 
    try:
       for existed_tab in existed_tabs:
          to_delete=True
          for admin_tab in used_admin_tabs:
              if existed_tab.key==admin_tab:
                 to_delete=False
          for io_tab in used_io_tabs:
              if existed_tab.key==io_tab:
                 to_delete=False
          if to_delete:
             existed_tab.key.delete()
    except:
      pass 

    #Tabs=Tab.query().filter(Tab.organization==org_key,Tab.) 
    yield op.db.Put(entity)
    yield op.counters.Increment('touched')