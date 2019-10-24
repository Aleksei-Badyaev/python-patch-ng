#!/usr/bin/env python
"""
python-patch test suite

There are two kind of tests:
 - file-based tests
 - directory-based tests
 - unit tests

File-based test is patch file, initial file and resulting file
for comparison.

Directory-based test is a self-sufficient directory with:
files to be patched, patch file itself and [result] dir. You can
manually apply patch and compare outcome with [result] directory.
This is what this test runner does.

Unit tests test API and are all inside this runner.


== Code Coverage ==

To refresh code coverage stats, get 'coverage' tool from
http://pypi.python.org/pypi/coverage/ and run this file with:

  coverage run run_tests.py
  coverage html -d coverage

On Windows it may be more convenient instead of `coverage` call
`python -m coverage.__main__`
"""
from __future__ import print_function

import os
import sys
import re
import shutil
import unittest
import copy
from os import listdir
from os.path import abspath, dirname, exists, join, isdir, isfile
from tempfile import mkdtemp
try:
  getcwdu = os.getcwdu
except AttributeError:
  getcwdu = os.getcwd  # python 3, where getcwd always returns a unicode object

verbose = False
if "-v" in sys.argv or "--verbose" in sys.argv:
  verbose = True


# full path for directory with tests
TESTS = dirname(abspath(__file__))
TESTDATA = join(TESTS, 'data')
def testfile(name):
  return join(TESTDATA, name)


# import patch_ng.py from parent directory
save_path = sys.path
sys.path.insert(0, dirname(TESTS))
import patch_ng
sys.path = save_path


# ----------------------------------------------------------------------------
class TestPatchFiles(unittest.TestCase):
  """
  unittest hack - test* methods are generated by add_test_methods() function
  below dynamically using information about *.patch files from tests directory

  """
  def _assert_files_equal(self, file1, file2):
      f1 = f2 = None
      try:
        f1 = open(file1, "rb")
        f2 = open(file2, "rb")
        for line in f1:
          self.assertEqual(line, f2.readline())

      finally:
        if f2:
          f2.close()
        if f1:
          f1.close()

  def _assert_dirs_equal(self, dir1, dir2, ignore=[]):
      """
      compare dir2 with reference dir1, ignoring entries
      from supplied list

      """
      # recursive
      if type(ignore) == str:
        ignore = [ignore]
      e2list = [en for en in listdir(dir2) if en not in ignore]
      for e1 in listdir(dir1):
        if e1 in ignore:
          continue
        e1path = join(dir1, e1)
        e2path = join(dir2, e1)
        self.assertTrue(exists(e1path))
        self.assertTrue(exists(e2path), "%s does not exist" % e2path)
        self.assertTrue(isdir(e1path) == isdir(e2path))
        if not isdir(e1path):
          self._assert_files_equal(e1path, e2path)
        else:
          self._assert_dirs_equal(e1path, e2path, ignore=ignore)
        e2list.remove(e1)
      for e2 in e2list:
        self.fail("extra file or directory: %s" % e2)


  def _run_test(self, testname):
      """
      boilerplate for running *.patch file tests
      """

      # 1. create temp test directory
      # 2. copy files
      # 3. execute file-based patch
      # 4. compare results
      # 5. cleanup on success

      tmpdir = mkdtemp(prefix="%s."%testname)

      basepath = join(TESTS, testname)
      basetmp = join(tmpdir, testname)

      patch_file = basetmp + ".patch"

      file_based = isfile(basepath + ".from")
      from_tgt = basetmp + ".from"

      if file_based:
        shutil.copy(basepath + ".from", tmpdir)
        shutil.copy(basepath + ".patch", tmpdir)
      else:
        # directory-based
        for e in listdir(basepath):
          epath = join(basepath, e)
          if not isdir(epath):
            shutil.copy(epath, join(tmpdir, e))
          else:
            shutil.copytree(epath, join(tmpdir, e))


      # 3.
      # test utility as a whole
      patch_tool = join(dirname(TESTS), "patch_ng.py")
      save_cwd = getcwdu()
      os.chdir(tmpdir)
      if verbose:
        cmd = '%s %s "%s"' % (sys.executable, patch_tool, patch_file)
        print("\n"+cmd)
      else:
        cmd = '%s %s -q "%s"' % (sys.executable, patch_tool, patch_file)
      ret = os.system(cmd)
      assert ret == 0, "Error %d running test %s" % (ret, testname)
      os.chdir(save_cwd)


      # 4.
      # compare results
      if file_based:
        self._assert_files_equal(basepath + ".to", from_tgt)
      else:
        # recursive comparison
        self._assert_dirs_equal(join(basepath, "[result]"),
                                tmpdir,
                                ignore=["%s.patch" % testname, ".svn", ".gitkeep", "[result]"])


      shutil.rmtree(tmpdir)
      return 0


def add_test_methods(cls):
    """
    hack to generate test* methods in target class - one
    for each *.patch file in tests directory
    """

    # list testcases - every test starts with number
    # and add them as test* methods
    testptn = re.compile(r"^(?P<name>\d{2,}[^\.]+).*$")

    testset = [testptn.match(e).group('name') for e in listdir(TESTS) if testptn.match(e)]
    testset = sorted(set(testset))

    for filename in testset:
      methname = 'test_' + filename
      def create_closure():
        name = filename
        return lambda self: self._run_test(name)
      test = create_closure()
      setattr(cls, methname, test)
      if verbose:
        print("added test method %s to %s" % (methname, cls))
add_test_methods(TestPatchFiles)

# ----------------------------------------------------------------------------

class TestCheckPatched(unittest.TestCase):
    def setUp(self):
        self.save_cwd = getcwdu()
        os.chdir(TESTS)

    def tearDown(self):
        os.chdir(self.save_cwd)

    def test_patched_multipatch(self):
        pto = patch_ng.fromfile("01uni_multi/01uni_multi.patch")
        os.chdir(join(TESTS, "01uni_multi", "[result]"))
        self.assertTrue(pto.can_patch(b"updatedlg.cpp"))

    def test_can_patch_single_source(self):
        pto2 = patch_ng.fromfile("02uni_newline.patch")
        self.assertTrue(pto2.can_patch(b"02uni_newline.from"))

    def test_can_patch_fails_on_target_file(self):
        pto3 = patch_ng.fromfile("03trail_fname.patch")
        self.assertEqual(None, pto3.can_patch(b"03trail_fname.to"))
        self.assertEqual(None, pto3.can_patch(b"not_in_source.also"))

    def test_multiline_false_on_other_file(self):
        pto = patch_ng.fromfile("01uni_multi/01uni_multi.patch")
        os.chdir(join(TESTS, "01uni_multi"))
        self.assertFalse(pto.can_patch(b"updatedlg.cpp"))

    def test_single_false_on_other_file(self):
        pto3 = patch_ng.fromfile("03trail_fname.patch")
        self.assertFalse(pto3.can_patch("03trail_fname.from"))

    def test_can_patch_checks_source_filename_even_if_target_can_be_patched(self):
        pto2 = patch_ng.fromfile("04can_patch.patch")
        self.assertFalse(pto2.can_patch("04can_patch_ng.to"))

# ----------------------------------------------------------------------------

class TestPatchParse(unittest.TestCase):
    def test_fromstring(self):
        try:
          f = open(join(TESTS, "01uni_multi/01uni_multi.patch"), "rb")
          readstr = f.read()
        finally:
          f.close()
        pst = patch_ng.fromstring(readstr)
        self.assertEqual(len(pst), 5)

    def test_fromfile(self):
        pst = patch_ng.fromfile(join(TESTS, "01uni_multi/01uni_multi.patch"))
        self.assertNotEqual(pst, False)
        self.assertEqual(len(pst), 5)
        ps2 = patch_ng.fromfile(testfile("failing/not-a-patch.log"))
        self.assertFalse(ps2)

    def test_no_header_for_plain_diff_with_single_file(self):
        pto = patch_ng.fromfile(join(TESTS, "03trail_fname.patch"))
        self.assertEqual(pto.items[0].header, [])

    def test_header_for_second_file_in_svn_diff(self):
        pto = patch_ng.fromfile(join(TESTS, "01uni_multi/01uni_multi.patch"))
        self.assertEqual(pto.items[1].header[0], b'Index: updatedlg.h\r\n')
        self.assertTrue(pto.items[1].header[1].startswith(b'====='))

    def test_hunk_desc(self):
        pto = patch_ng.fromfile(testfile('git-changed-file.diff'))
        self.assertEqual(pto.items[0].hunks[0].desc, b'class JSONPluginMgr(object):')

    def test_autofixed_absolute_path(self):
        pto = patch_ng.fromfile(join(TESTS, "data/autofix/absolute-path.diff"))
        self.assertEqual(pto.errors, 0)
        self.assertEqual(pto.warnings, 9)
        self.assertEqual(pto.items[0].source, b"winnt/tests/run_tests.py")

    def test_autofixed_parent_path(self):
        # [ ] exception vs return codes for error recovery
        #  [x] separate return code when patch lib compensated the error
        #      (implemented as warning count)
        pto = patch_ng.fromfile(join(TESTS, "data/autofix/parent-path.diff"))
        self.assertEqual(pto.errors, 0)
        self.assertEqual(pto.warnings, 4)
        self.assertEqual(pto.items[0].source, b"patch_ng.py")

    def test_autofixed_stripped_trailing_whitespace(self):
        pto = patch_ng.fromfile(join(TESTS, "data/autofix/stripped-trailing-whitespace.diff"))
        self.assertEqual(pto.errors, 0)
        self.assertEqual(pto.warnings, 4)

    def test_fail_missing_hunk_line(self):
        fp = open(join(TESTS, "data/failing/missing-hunk-line.diff"), 'rb')
        pto = patch_ng.PatchSet()
        self.assertNotEqual(pto.parse(fp), True)
        fp.close()

    def test_fail_context_format(self):
        fp = open(join(TESTS, "data/failing/context-format.diff"), 'rb')
        res = patch_ng.PatchSet().parse(fp)
        self.assertFalse(res)
        fp.close()

    def test_fail_not_a_patch(self):
        fp = open(join(TESTS, "data/failing/not-a-patch.log"), 'rb')
        res = patch_ng.PatchSet().parse(fp)
        self.assertFalse(res)
        fp.close()

    def test_diffstat(self):
        output = """\
 updatedlg.cpp | 20 ++++++++++++++++++--
 updatedlg.h   |  1 +
 manifest.xml  | 15 ++++++++-------
 conf.cpp      | 23 +++++++++++++++++------
 conf.h        |  7 ++++---
 5 files changed, 48 insertions(+), 18 deletions(-), +1203 bytes"""
        pto = patch_ng.fromfile(join(TESTS, "01uni_multi/01uni_multi.patch"))
        self.assertEqual(pto.diffstat(), output, "Output doesn't match")


class TestPatchSetDetection(unittest.TestCase):
    def test_svn_detected(self):
        pto = patch_ng.fromfile(join(TESTS, "01uni_multi/01uni_multi.patch"))
        self.assertEqual(pto.type, patch_ng.SVN)

# generate tests methods for TestPatchSetDetection - one for each patch file
def generate_detection_test(filename, patchtype):
  # saving variable in local scope to prevent test()
  # from fetching it from global
  patchtype = difftype
  def test(self):
    pto = patch_ng.fromfile(join(TESTDATA, filename))
    self.assertEqual(pto.type, patchtype)
  return test

for filename in os.listdir(TESTDATA):
  if isdir(join(TESTDATA, filename)):
    continue

  difftype = patch_ng.PLAIN
  if filename.startswith('git-'):
    difftype = patch_ng.GIT
  if filename.startswith('hg-'):
    difftype = patch_ng.HG
  if filename.startswith('svn-'):
    difftype = patch_ng.SVN

  name = 'test_'+filename
  test = generate_detection_test(filename, difftype)
  setattr(TestPatchSetDetection, name, test)
  if verbose:
    print("added test method %s to %s" % (name, 'TestPatchSetDetection'))


class TestPatchApply(unittest.TestCase):
    def setUp(self):
        self.save_cwd = getcwdu()
        self.tmpdir = mkdtemp(prefix=self.__class__.__name__)
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.save_cwd)
        shutil.rmtree(self.tmpdir)

    def tmpcopy(self, filenames):
        """copy file(s) from test_dir to self.tmpdir"""
        for f in filenames:
          shutil.copy(join(TESTS, f), self.tmpdir)

    def test_apply_returns_false_on_failure(self):
        self.tmpcopy(['data/failing/non-empty-patch-for-empty-file.diff',
                      'data/failing/upload.py'])
        pto = patch_ng.fromfile('non-empty-patch-for-empty-file.diff')
        self.assertFalse(pto.apply())

    def test_apply_returns_true_on_success(self):
        self.tmpcopy(['03trail_fname.patch',
                      '03trail_fname.from'])
        pto = patch_ng.fromfile('03trail_fname.patch')
        self.assertTrue(pto.apply())

    def test_revert(self):
        def get_file_content(filename):
            with open(filename, 'rb') as f:
                return f.read()

        self.tmpcopy(['03trail_fname.patch',
                      '03trail_fname.from'])
        pto = patch_ng.fromfile('03trail_fname.patch')
        self.assertTrue(pto.apply())
        self.assertNotEqual(get_file_content(self.tmpdir + '/03trail_fname.from'),
                            get_file_content(TESTS + '/03trail_fname.from'))
        self.assertTrue(pto.revert())
        self.assertEqual(get_file_content(self.tmpdir + '/03trail_fname.from'),
                         get_file_content(TESTS + '/03trail_fname.from'))

    def test_apply_root(self):
        treeroot = join(self.tmpdir, 'rootparent')
        shutil.copytree(join(TESTS, '06nested'), treeroot)
        pto = patch_ng.fromfile(join(TESTS, '06nested/06nested.patch'))
        self.assertTrue(pto.apply(root=treeroot))

    def test_apply_strip(self):
        treeroot = join(self.tmpdir, 'rootparent')
        shutil.copytree(join(TESTS, '06nested'), treeroot)
        pto = patch_ng.fromfile(join(TESTS, '06nested/06nested.patch'))
        for p in pto:
          p.source = b'nasty/prefix/' + p.source
          p.target = b'nasty/prefix/' + p.target
        self.assertTrue(pto.apply(strip=2, root=treeroot))

    def test_create_file(self):
        treeroot = join(self.tmpdir, 'rootparent')
        os.makedirs(treeroot)
        pto = patch_ng.fromfile(join(TESTS, '08create/08create.patch'))
        pto.apply(strip=0, root=treeroot)
        self.assertTrue(os.path.exists(os.path.join(treeroot, 'created')))

    def test_delete_file(self):
        treeroot = join(self.tmpdir, 'rootparent')
        shutil.copytree(join(TESTS, '09delete'), treeroot)
        pto = patch_ng.fromfile(join(TESTS, '09delete/09delete.patch'))
        pto.apply(strip=0, root=treeroot)
        self.assertFalse(os.path.exists(os.path.join(treeroot, 'deleted')))

    def test_fuzzy(self):
        treeroot = join(self.tmpdir, 'rootparent')
        shutil.copytree(join(TESTS, '10fuzzy'), treeroot)
        pto = patch_ng.fromfile(join(TESTS, '10fuzzy/10fuzzy.patch'))
        pto.apply(strip=0, root=treeroot)


class TestHelpers(unittest.TestCase):
    # unittest setting
    longMessage = True

    absolute = [b'/', b'c:\\', b'c:/', b'\\', b'/path', b'c:\\path']
    relative = [b'path', b'path:\\', b'path:/', b'path\\', b'path/', b'path\\path']

    def test_xisabs(self):
        for path in self.absolute:
            self.assertTrue(patch_ng.xisabs(path), 'Target path: ' + repr(path))
        for path in self.relative:
            self.assertFalse(patch_ng.xisabs(path), 'Target path: ' + repr(path))

    def test_xnormpath(self):
        path = b"../something/..\\..\\file.to.patch"
        self.assertEqual(patch_ng.xnormpath(path), b'../../file.to.patch')

    def test_xstrip(self):
        for path in self.absolute[:4]:
            self.assertEqual(patch_ng.xstrip(path), b'')
        for path in self.absolute[4:6]:
            self.assertEqual(patch_ng.xstrip(path), b'path')
        # test relative paths are not affected
        for path in self.relative:
            self.assertEqual(patch_ng.xstrip(path), path)

    def test_pathstrip(self):
        self.assertEqual(patch_ng.pathstrip(b'path/to/test/name.diff', 2), b'test/name.diff')
        self.assertEqual(patch_ng.pathstrip(b'path/name.diff', 1), b'name.diff')
        self.assertEqual(patch_ng.pathstrip(b'path/name.diff', 0), b'path/name.diff')

# ----------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main()
