"""Snapshot destination matches Omasnap and a saved shot is its newest recent entry."""
import importlib.util,os,json,io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
spec=importlib.util.spec_from_file_location('snapshots',Path(__file__).resolve().parent.parent/'bin/snapshot_files.py');snapshots=importlib.util.module_from_spec(spec);spec.loader.exec_module(snapshots)
class SnapshotOS(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT']);self.root=Path(self.temp.name)
  self.environment=patch.dict(os.environ,{},clear=False);self.environment.start()
  for key in ('WEBCAMTUNER_SNAPSHOT_ROOT','OMASNAP_SCREENSHOT_DIR','OMARCHY_SCREENSHOT_DIR'):os.environ.pop(key,None)
  os.environ.update(XDG_CONFIG_HOME=str(self.root/'config'),XDG_DATA_HOME=str(self.root/'data'),OMASNAP_RECENT_DIR=str(self.root/'recent'),WEBCAMTUNER_CONFIG_ROOT=str(self.root/'plugin-config'))
  config=self.root/'config/omasnap';config.mkdir(parents=True);(config/'omasnap.conf').write_text('[output]\ndirectory = '+str(self.root/'OS shots')+'\n')
 def tearDown(self):self.environment.stop();self.temp.cleanup()
 def test_os_config_and_environment_precedence(self):
  self.assertEqual(snapshots.os_directory(False),self.root/'OS shots')
  os.environ['OMASNAP_SCREENSHOT_DIR']=str(self.root/'Env shots');self.assertEqual(snapshots.os_directory(False),self.root/'Env shots')
 def test_native_qt_recent_directory_includes_the_organization(self):
  from PySide6.QtCore import QCoreApplication,QStandardPaths
  app=QCoreApplication.instance() or QCoreApplication(['omasnap'])
  app.setApplicationName('omasnap');app.setOrganizationName('Omarchy')
  os.environ['XDG_STATE_HOME']=str(self.root/'state');os.environ.pop('OMASNAP_RECENT_DIR',None)
  expected=Path(QStandardPaths.writableLocation(QStandardPaths.StateLocation))/'recent'
  data=io.BytesIO();Image.new('RGB',(80,60),'blue').save(data,'JPEG');path=snapshots.save(data.getvalue())
  result=snapshots.mirror_snapshot(path);self.assertNotIn('recentError',result)
  self.assertEqual(Path(result['recentThumbnail']).parent,expected)
 def test_newest_private_recent_document_reopens_the_saved_pixels(self):
  data=io.BytesIO();Image.new('RGB',(640,360),'#246080').save(data,'JPEG')
  path=snapshots.save(data.getvalue());self.assertEqual(path.parent,self.root/'data/webcamtuner/snapshots')
  previous=snapshots.mirror_snapshot(path);self.assertNotIn('recentError',previous)
  latest=snapshots.mirror_snapshot(path);self.assertNotIn('recentError',latest)
  thumbs=sorted((self.root/'recent').glob('*.thumb.png'),reverse=True)
  self.assertEqual(str(thumbs[0]),latest['recentThumbnail'])
  stem=thumbs[0].name.removesuffix('.thumb.png')
  log=json.loads((self.root/'recent'/(stem+'.json')).read_text())
  self.assertEqual(log['recentId'],latest['recentId']);self.assertEqual(log['savedPath'],latest['mirrorPath']);self.assertEqual(log['ops'],[])
  with Image.open(self.root/'recent'/(stem+'.png')) as source: self.assertEqual(source.size,(640,360));self.assertLess(abs(source.getpixel((20,20))[0]-36),3)
  self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in (self.root/'recent').iterdir() if p.is_file()))
  self.assertFalse(list((self.root/'recent').glob('*.partial')))
 def test_disabling_mirror_keeps_only_the_local_original(self):
  snapshots.save_settings(False);self.assertFalse(snapshots.read_settings()['mirrorToOS'])
  data=io.BytesIO();Image.new('RGB',(80,60),'blue').save(data,'JPEG');path=snapshots.save(data.getvalue())
  self.assertEqual(snapshots.mirror_snapshot(path),{'mirrored':False})
  self.assertTrue(path.exists());self.assertFalse((self.root/'OS shots').exists());self.assertFalse((self.root/'recent').exists())
if __name__=='__main__':unittest.main()
