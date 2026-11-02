#!/usr/bin/env python3
"""Private local snapshots with optional verified OS mirror and Omasnap recents."""
from datetime import datetime
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid
import configparser
import io
import time
import fcntl
from PIL import Image


def directory(create=True):
    target=Path(os.environ.get('WEBCAMTUNER_SNAPSHOT_ROOT') or Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'webcamtuner/snapshots')
    if not target.is_absolute(): raise ValueError('Snapshot folder must be an absolute path.')
    if create: target.mkdir(parents=True,exist_ok=True,mode=0o700)
    return target


def os_directory(create=False):
    config=configparser.ConfigParser(interpolation=None)
    config.read(Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'omasnap/omasnap.conf')
    configured=os.environ.get('OMASNAP_SCREENSHOT_DIR') or os.environ.get('OMARCHY_SCREENSHOT_DIR') or config.get('output','directory',fallback='').strip()
    if configured: target=Path(configured).expanduser().absolute()
    else:
        try:
            result=subprocess.run(['xdg-user-dir','PICTURES'],capture_output=True,text=True,timeout=3)
            pictures=Path(result.stdout.strip()) if result.returncode==0 and result.stdout.strip() else Path.home()/'Pictures'
        except (OSError,subprocess.TimeoutExpired): pictures=Path.home()/'Pictures'
        target=pictures/'Screenshots'
    if not target.is_absolute(): raise ValueError('OS screenshot folder must be an absolute path.')
    if create: target.mkdir(parents=True,exist_ok=True,mode=0o700)
    return target


def read_settings():
    path=Path(os.environ.get('WEBCAMTUNER_CONFIG_ROOT') or Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'webcamtuner')/'snapshots.json'
    if not path.exists(): return {'schemaVersion':1,'mirrorToOS':True}
    if path.stat().st_size>4096:raise ValueError('Snapshot settings exceed their size limit.')
    value=json.loads(path.read_text())
    if not isinstance(value,dict) or value.get('schemaVersion')!=1 or not isinstance(value.get('mirrorToOS'),bool):raise ValueError('Invalid snapshot settings.')
    return value


def save_settings(mirror):
    if not isinstance(mirror,bool):raise ValueError('Choose whether to mirror snapshots.')
    root=Path(os.environ.get('WEBCAMTUNER_CONFIG_ROOT') or Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'webcamtuner')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(root/'snapshots.json.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        read_settings()
        path=root/'snapshots.json';temporary=root/('.'+uuid.uuid4().hex+'.partial')
        try:
            with temporary.open('xb') as stream:
                os.chmod(temporary,0o600);stream.write((json.dumps({'schemaVersion':1,'mirrorToOS':mirror})+'\n').encode());stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path)
            directory_fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory_fd)
            finally:os.close(directory_fd)
        finally:temporary.unlink(missing_ok=True)
        if read_settings()['mirrorToOS']!=mirror:raise ValueError('Snapshot mirror setting could not be verified.')
    finally:os.close(fd)
    return read_settings()


def mirror_snapshot(path):
    # Existing isolated snapshot tests must never copy into the operator's folders.
    if os.environ.get('WEBCAMTUNER_SNAPSHOT_ROOT') and not os.environ.get('OMASNAP_SCREENSHOT_DIR') and not os.environ.get('OMASNAP_RECENT_DIR'):return {}
    try:
        if not read_settings()['mirrorToOS']:return {'mirrored':False}
        folder=os_directory(create=True);target=folder/(path.stem+'.png')
        if target.absolute()!=path.absolute():
            encoded=io.BytesIO()
            with Image.open(path) as photo:photo.convert('RGB').save(encoded,'PNG')
            data=encoded.getvalue()
            if target.exists():target=folder/(path.stem+'-'+uuid.uuid4().hex[:8]+'.png')
            temporary=folder/('.'+uuid.uuid4().hex+'.partial')
            try:
                with temporary.open('xb') as stream:
                    os.chmod(temporary,0o600);stream.write(data);stream.flush();os.fsync(stream.fileno())
                os.link(temporary,target)
                if hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(data).digest():raise ValueError('OS snapshot copy could not be verified.')
                fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(fd)
                finally:os.close(fd)
            finally:temporary.unlink(missing_ok=True)
        return {'mirrored':True,'mirrorPath':str(target),**record_recent(target)}
    except (OSError,ValueError,configparser.Error) as error:
        return {'mirrorError':'Snapshot saved locally; could not mirror to OS screenshots: '+str(error)[:200]}


def record_recent(path):
    """Omasnap 1.24's source/log/thumbnail contract; publish thumbnail last."""
    if os.environ.get('WEBCAMTUNER_SNAPSHOT_ROOT') and not os.environ.get('OMASNAP_RECENT_DIR'):
        return {}
    try:
        from PySide6.QtCore import QLockFile
        version = subprocess.check_output(['omasnap','--version'],text=True,timeout=3).strip()
        if not version.startswith('omasnap 1.24.'):
            return {'recentError':'Snapshot saved; this Omasnap version does not support the verified recent-images adapter.'}
        root = Path(os.environ.get('OMASNAP_RECENT_DIR') or Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local/state')/'omasnap/recent')
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        if root.is_symlink() or root.stat().st_uid != os.getuid(): raise ValueError('Recent-images folder is not user-owned.')
        root.chmod(0o700)
        recent_id = uuid.uuid4().hex
        pending = QLockFile(str(root/('.pending-'+recent_id+'.lock')))
        if not pending.tryLock(5000): raise ValueError('Recent image is still being saved.')
        with Image.open(path) as source:
            image=source.convert('RGB'); original=io.BytesIO();image.save(original,'PNG')
            size=image.size;image.thumbnail((320,320));thumb=io.BytesIO();image.save(thumb,'PNG')
        lock=QLockFile(str(root/'.record.lock'))
        if not lock.tryLock(5000): raise ValueError('Omasnap recent images are busy.')
        written=[]
        try:
            stem=f'{time.time_ns()//1_000_000:016d}-{recent_id}'
            document={'version':1,'index':0,'nextId':'1','nextMarker':1,'recentId':recent_id,'savedPath':str(path),'previewWidth':size[0],'previewHeight':size[1],'ops':[]}
            for suffix,data in [('.png',original.getvalue()),('.json',(json.dumps(document)+'\n').encode()),('.thumb.png',thumb.getvalue())]:
                target=root/(stem+suffix);temporary=root/('.'+uuid.uuid4().hex+'.partial')
                try:
                    with temporary.open('xb') as stream:
                        os.chmod(temporary,0o600);stream.write(data);stream.flush();os.fsync(stream.fileno())
                    os.replace(temporary,target);written.append(target)
                    if hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(data).digest(): raise ValueError('Recent image verification failed.')
                finally: temporary.unlink(missing_ok=True)
            fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        except Exception:
            for file in reversed(written):file.unlink(missing_ok=True)
            raise
        finally:
            lock.unlock();pending.unlock()
        return {'recentId':recent_id,'recentThumbnail':str(root/(stem+'.thumb.png'))}
    except (OSError,ValueError,ImportError,subprocess.SubprocessError) as error:
        return {'recentError':'Snapshot saved; could not update Omasnap recent images: '+str(error)[:200]}


def save(jpeg):
    if not jpeg.startswith(b'\xff\xd8') or not jpeg.endswith(b'\xff\xd9') or len(jpeg) > 50 * 1024 * 1024:
        raise ValueError('Snapshot encoding was not a complete JPEG.')
    folder = directory()
    name = 'WebcamTuner-' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f') + '-' + uuid.uuid4().hex[:8] + '.jpg'
    target = folder / name
    temporary = folder / ('.' + uuid.uuid4().hex + '.partial')
    try:
        with temporary.open('xb') as stream:
            os.chmod(temporary, 0o600)
            stream.write(jpeg)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(jpeg).digest():
            raise ValueError('Snapshot save could not be verified.')
    finally:
        temporary.unlink(missing_ok=True)
    return target


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create',action='store_true')
    parser.add_argument('--mirror-os',choices=['true','false'])
    args=parser.parse_args()
    try:
        settings=save_settings(args.mirror_os=='true') if args.mirror_os is not None else read_settings()
        print(json.dumps({**settings,'directory':str(directory(create=args.create)),'osDirectory':str(os_directory())}))
    except (OSError,ValueError,configparser.Error) as error:
        print(json.dumps({'error':str(error)}))
        raise SystemExit(1)
