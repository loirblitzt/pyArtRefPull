#dirty sys path trick, plz look away
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyartrefpull


def test_getUserId():
    id_value = pyartrefpull.getUserId('dudlswns3')
    print(id_value)
    assert "161249" == id_value

def test_getUserCollections():
    mJson = pyartrefpull.getUserCollections("82957")
    assert len(mJson) >= 1
    assert mJson[0]["name"] == "feel"

def test_getUserLikes():
    mJson = pyartrefpull.getUserLikes("arowana")
    assert mJson is not None
    assert len(mJson["data"]) == 50
    assert mJson["total_count"] >=108

def test_getCollectionProjects():
    mJson = pyartrefpull.getCollectionProjects(310180)
    assert mJson is not None
    assert len(mJson["data"]) == 50
    assert mJson["total_count"] >= 900

def test_getArtistProjects():
    mJson = pyartrefpull.getArtistProjects("dudlswns3")
    assert mJson is not None
    # assert len(mJson["data"]) >= 7
    # assert mJson["total_count"] >= 7

def test_playwrightArtRequest():
    res = pyartrefpull.playwrightArtRequest(
        "https://www.artstation.com/users/dudlswns3/likes.json?page=1"
        )
    assert res.status == 200