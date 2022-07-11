import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyartrefpull

def test_libSettingLoad():
    res = pyartrefpull.loadLibrarySettings(os.path.dirname(__file__), "../sample_libSettings.yaml")
    assert res is not None
    assert len(res["sources"]) >= 1


def test_libSettingLoad_nofile():
    res = pyartrefpull.loadLibrarySettings(
        os.path.dirname(__file__), "../sample_libSettingsBIT.yaml")
    assert res is None

def test_cacheLoad_nofile():
    resList, resColums,artDict = pyartrefpull.loadCacheFile(os.path.dirname(
        __file__), "../sample_BIte.csv")
    assert len(resList) == 0
    assert resColums is None
    assert len(artDict)  == 0
