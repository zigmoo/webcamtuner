"""Verify durable local copies, safe decoding and thumbnail recovery."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from PIL import Image

spec = importlib.util.spec_from_file_location('library', Path(__file__).resolve().parent.parent / 'bin/background-library.py')
library = importlib.util.module_from_spec(spec)
spec.loader.exec_module(library)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT'])
        self.root = Path(self.scratch.name)
        self.environment = dict(os.environ)
        os.environ['WEBCAMTUNER_CONFIG_ROOT'] = str(self.root / 'config')
        os.environ['XDG_DATA_HOME'] = str(self.root / 'data')
        os.environ['XDG_CACHE_HOME'] = str(self.root / 'cache')
        self.source = self.root / "My #1 background.jpeg"
        image = Image.new('RGB', (40, 20), 'purple')
        exif = image.getexif(); exif[274] = 6
        image.save(self.source, exif=exif)

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.environment)
        self.scratch.cleanup()

    def test_copy_survives_original_removal_and_deduplicates_by_bytes(self):
        original = self.source.read_bytes()
        result = library.add([self.source.as_uri()])
        self.assertFalse(result['errors'])
        entry = result['added'][0]
        copied = Path(entry['path'])
        self.assertEqual(copied.parent, self.root / 'data/webcamtuner/backgrounds')
        self.assertEqual(copied.read_bytes(), original)
        self.assertEqual(copied.stat().st_mode & 0o777, 0o600)
        other = self.root / 'Different name.png'; other.write_bytes(original)
        self.assertEqual(library.add([str(other)])['added'][0]['id'], entry['id'])
        self.source.unlink(); other.unlink()
        self.assertEqual(len(library.listing()['items']), 1)
        thumb = library.local_path(entry['thumbnail'])
        with Image.open(thumb) as image:
            self.assertEqual(image.size, (20, 40))  # EXIF orientation is honored.
        thumb.unlink()
        self.assertTrue(library.listing()['items'][0]['thumbnail'])
        self.assertTrue(thumb.exists())

    def test_invalid_and_animated_inputs_do_not_prevent_valid_import(self):
        broken = self.root / 'fake.jpg'; broken.write_text('not an image')
        animated = self.root / 'animated.webp'
        Image.new('RGB', (10, 10), 'red').save(animated, save_all=True, append_images=[Image.new('RGB', (10, 10), 'blue')], duration=100, loop=0)
        result = library.add([str(broken), str(animated), str(self.source)])
        self.assertEqual(len(result['errors']), 2)
        self.assertEqual(len(result['added']), 1)
        self.assertEqual(len(result['items']), 1)

    def test_fifo_and_oversized_inputs_are_rejected_without_blocking(self):
        fifo = self.root / 'pipe.jpg'; os.mkfifo(fifo)
        huge = self.root / 'huge.jpg'
        with huge.open('wb') as stream:
            stream.truncate(library.MAX_BYTES + 1)
        result = library.add([str(fifo), str(huge)])
        self.assertEqual(len(result['errors']), 2)
        self.assertEqual(result['items'], [])

    def test_symlinks_in_library_are_ignored_and_cannot_overwrite_external_files(self):
        result = library.add([str(self.source)])
        path = Path(result['added'][0]['path'])
        path.unlink(); path.symlink_to(self.source)
        result = library.add([str(self.source)])
        self.assertEqual(len(result['errors']), 1)
        self.assertTrue(self.source.exists())
        self.assertEqual(result['items'], [])

    def test_external_files_appear_update_and_disappear_without_renaming(self):
        folder, _ = library.directories()
        first = folder / 'Beach.JPG'
        second = folder / 'Forest.png'
        first.write_bytes(self.source.read_bytes())
        Image.new('RGB', (80, 40), 'green').save(second)
        initial = library.listing()
        self.assertEqual({x['name'] for x in initial['items']}, {'Beach.JPG', 'Forest.png'})
        old = next(x for x in initial['items'] if x['name'] == 'Forest.png')
        Image.new('RGB', (80, 40), 'blue').save(second)
        new = next(x for x in library.listing()['items'] if x['name'] == 'Forest.png')
        self.assertNotEqual(old['id'], new['id'])
        self.assertNotEqual(old['thumbnail'], new['thumbnail'])
        first.unlink()
        self.assertEqual([x['name'] for x in library.listing()['items']], ['Forest.png'])

    def test_each_image_remembers_crop_by_content_across_selection_and_restart(self):
        first = library.add([str(self.source)])['added'][0]
        other = self.root / 'Other.png'; Image.new('RGB', (60, 40), 'orange').save(other)
        second = library.add([str(other)])['added'][0]
        crop = {'zoom': 2.2, 'centerX': 0.7, 'centerY': 0.4}
        library.save_crop(first['path'], crop)
        selected = library.listing(second['path'])['selected']
        self.assertEqual(selected['crop'], library.default_crop())
        self.assertEqual(library.listing(first['path'])['selected']['crop'], crop)
        self.assertEqual(library.add([str(self.source)])['added'][0]['crop'], crop)
        self.assertEqual(library.crop_file().stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            library.save_crop(first['path'], {'zoom': 0, 'centerX': 0.5, 'centerY': 0.5})
        self.assertEqual(library.listing(first['path'])['selected']['crop'], crop)

    def test_path_and_batch_limits(self):
        for values in ([], ['relative.jpg'], ['https://example.com/image.jpg'], [str(self.source)] * 21):
            if len(values) in (0, 21):
                with self.assertRaises(ValueError): library.add(values)
            else:
                self.assertEqual(len(library.add(values)['errors']), 1)


if __name__ == '__main__':
    unittest.main()
