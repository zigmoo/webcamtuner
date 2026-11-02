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

    def test_path_and_batch_limits(self):
        for values in ([], ['relative.jpg'], ['https://example.com/image.jpg'], [str(self.source)] * 21):
            if len(values) in (0, 21):
                with self.assertRaises(ValueError): library.add(values)
            else:
                self.assertEqual(len(library.add(values)['errors']), 1)


if __name__ == '__main__':
    unittest.main()
