"""Exercise lock/readback and OS trash/profile updates through the public controller."""
import json,os,subprocess,tempfile
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT']) as tmp:
 scratch=Path(tmp);env=dict(os.environ,WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
 def cli(operation,*args):
  r=subprocess.run([str(root/'bin/webcamtuner'),operation,*args,'--json'],env=env,capture_output=True,text=True)
  assert r.returncode==0,r.stderr
  return json.loads(r.stdout)
 source=scratch/'Image.png';Image.new('RGB',(80,60),'orange').save(source)
 image=cli('add-backgrounds','--paths',json.dumps([str(source)]))['added'][0]
 args=['--path',image['path'],'--id',image['id']]
 result=cli('label-background',*args,'--label','Morning light');assert result['items'][0]['label']=='Morning light'
 result=cli('lock-background',*args,'--locked','true');assert result['items'][0]['locked']
 result=cli('lock-background',*args,'--locked','false');assert not result['items'][0]['locked']
 document=cli('read');document['profiles'][0]['background']={'mode':'image','imagePath':image['path']};document['profiles'][0]['crop']={'zoom':2,'centerX':.5,'centerY':.5}
 saved=cli('save','--document',json.dumps(document))
 result=cli('trash-background',*args)
 assert not Path(image['path']).exists() and not result['items']
 assert result['document']['profiles'][0]['background']['mode']=='blur'
 assert result['document']['profiles'][0]['crop']==saved['profiles'][0]['crop']
 assert cli('read')==result['document']
 assert len(list((scratch/'data/Trash/files').iterdir()))==1
 # A failed OS move must restore profile data and report the new revision.
 image=cli('add-backgrounds','--paths',json.dumps([str(source)]))['added'][0];args=['--path',image['path'],'--id',image['id']]
 document=cli('read');document['profiles'][0]['background']={'mode':'image','imagePath':image['path']};saved=cli('save','--document',json.dumps(document))
 fake=scratch/'fake';fake.mkdir();(fake/'gio').write_text('#!/bin/sh\necho "Test Trash unavailable" >&2\nexit 1\n');(fake/'gio').chmod(0o755)
 env['PATH']=str(fake)+os.pathsep+env['PATH']
 result=cli('trash-background',*args)
 assert result['trashError'] and Path(image['path']).exists()
 assert result['document']['profiles']==saved['profiles']
 assert result['document']==cli('read')
 print('PASS: lock readback; OS Trash; safe profile updates; failed-move rollback with revision readback')
