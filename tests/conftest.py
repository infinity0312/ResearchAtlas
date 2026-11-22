import os,tempfile
os.environ['ATLAS_DATA']=tempfile.mkdtemp(prefix='atlas-tests-')
os.environ['ATLAS_SCOPED_INTAKE_DISABLED']='1'
import pytest
from backend.db import Base,engine,init_db
@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine); init_db()
