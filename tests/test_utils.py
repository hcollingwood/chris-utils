import tempfile

from chris_utils.utils import get_version, get_list_of_files


def test_get_list_of_files(fs):
    top_level_path = '/home/top_level'
    subdir_path = '/home/top_level/subdir'
    cog_path = '/home/top_level/subdir/cog/cog.cog'
    zarr_path = '/home/top_level/subdir/zarr/zarr.zarr'
    safe_path = '/home/top_level/subdir/safe/safe.SAFE'
    unrelated_path = '/home/top_level/subdir/other/other.other'
    paths = [top_level_path, subdir_path, cog_path, zarr_path, safe_path, unrelated_path]

    for p in paths:
        fs.create_dir(p)
    fs.create_file(f"{top_level_path}/this/is/a/file.txt")

    list_of_files = get_list_of_files([top_level_path])
    assert len(list_of_files) == 3
    assert cog_path in list_of_files
    assert zarr_path in list_of_files
    assert safe_path in list_of_files


def test_get_version():
    root = "file_root"
    suffix = ".sfx"

    with tempfile.TemporaryDirectory() as tmpdir:
        version = get_version(root, suffix, tmpdir)
        assert version == "0001"

        with open(f"{tmpdir}/{root}_0001{suffix}", 'w') as f:
            f.write("file contents")

        version = get_version(root, suffix, tmpdir)
        assert version == "0002"
