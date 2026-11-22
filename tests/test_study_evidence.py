import pytest
from backend.study_evidence import Inventory,owned_inventory


def test_scope_projection_retains_cross_page_evidence_without_guessing():
    context={f'p{i}b1':dict(page=i,text='source') for i in range(1,4)}
    v=Inventory(pages=[dict(page=i,role='method',content='method content') for i in range(1,4)],facts=[
        dict(kind='method',statement='cross page method',condition='same method',evidence_ids=['p1b1','p2b1']),
        dict(kind='method',statement='neighbour only fact',condition='other section',evidence_ids=['p3b1'])])
    result=owned_inventory(v,{1,2},context)
    assert [p.page for p in result.pages]==[1,2]
    assert len(result.facts)==1 and result.facts[0].evidence_ids==['p1b1','p2b1']
    result.pages.pop()
    with pytest.raises(ValueError,match='every assigned'):owned_inventory(result,{1,2},context)

def test_missing_facts_gets_bounded_repair_and_source_changes_rejected(tmp_path):
 from backend.study_evidence import collect
 class Provider:
  config={'model':'test'}
  count=0
  def generate(self,prompt):
   self.count+=1
   page=dict(page=1,role='method',content='A documented method')
   if self.count==1:return {'pages':[page]}
   assert 'facts' in prompt and 'Validation feedback' in prompt
   return {'pages':[page],'facts':[dict(kind='method',statement='A documented scientific method',condition='under this setting',evidence_ids=['p1b1'])]}
 provider=Provider();pages=[{'page':1,'text':'A documented scientific method under this setting.'}]
 result=collect(provider,pages,tmp_path,'test')
 assert provider.count==2 and result['facts']==1
 collect(provider,pages,tmp_path,'test');assert provider.count==2
 with pytest.raises(ValueError,match='Source changed'):
  collect(provider,[{'page':1,'text':'A different source.'}],tmp_path,'test')
