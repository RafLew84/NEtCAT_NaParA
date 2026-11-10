"""Explicit download of pinned official code/weights; measurement data never leaves disk."""
import argparse
from pathlib import Path
import shutil
import tarfile
import urllib.request
from stmdomains.experiments.bundle import file_hash,write_json
from .models import ASSETS,DINO_PIN

ARCHIVE_SHA='c27dcdaf50e9fb5bbdf2bb529da357716372e19c6afab17d5350f3f0094aed4b'


def download(url,path,expected):
    if not path.exists():
        partial=path.with_suffix(path.suffix+'.part')
        with urllib.request.urlopen(url) as source,partial.open('wb') as target:
            shutil.copyfileobj(source,target)
        if file_hash(partial)!=expected:
            raise ValueError('Downloaded file hash differs from pinned asset')
        partial.replace(path)
    if file_hash(path)!=expected:
        raise ValueError('Existing asset hash mismatch')


def prepare(path):
    path.mkdir(parents=True,exist_ok=True)
    for asset in ASSETS.values():download(asset['url'],path/asset['file'],asset['sha256'])
    url=f'https://codeload.github.com/facebookresearch/dinov2/tar.gz/{DINO_PIN}'
    archive=path/'dinov2-source.tar.gz';download(url,archive,ARCHIVE_SHA)
    if not (path/('dinov2-'+DINO_PIN)).exists():
        with tarfile.open(archive) as source:source.extractall(path,filter='data')
    write_json(path/'sources.json',dict(dinov2_commit=DINO_PIN,dinov2_code_url=url,archive_sha256=ARCHIVE_SHA,weights=ASSETS))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.out)
