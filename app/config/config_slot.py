"""Verified built-in island-slot templates.

Generated from the supplied slot XML corpus. These data are complete Gamedata
object clones, not minimal reconstructions. Target-island templates still take
priority; this library is the fallback when the requested slot GUID is absent.
"""
from __future__ import annotations
import copy
import app.backend.xml_backend as ET
SLOT_LIBRARY_VERSION = 2

RIVER_GUID_FAMILIES = {
    "native": {
        "primary": "117741", "workarea": "1999002331",
        "primary_group": "15", "workarea_group": "3",
        "folder_pairing": True,
    },
    "custom_a": {
        "primary": "1999002330", "workarea": "1999002331",
        "primary_group": "15", "workarea_group": "3",
        "folder_pairing": False,
    },
    "custom_b": {
        "primary": "1999002336", "workarea": "1999002337",
        "primary_group": "15", "workarea_group": "3",
        "folder_pairing": False,
    },
}
RIVER_GUID_ROLE = {
    guid: (family, role)
    for family, definition in RIVER_GUID_FAMILIES.items()
    for role, guid in (("primary", definition["primary"]),
                       ("workarea", definition["workarea"]))
}
SINGLE_SLOT_GUIDS = {"100417", "100849", "113750"}
RESOURCE_SLOT_NAMES = {"100417": "clay slot", "100849": "oil slot", "113750": "gas slot (arctic)"}
SLOT_DEFINITIONS = {
    "Riverslot": {"guid": "117741", "group": "15", "pair": "Riverslot_workarea", "pair_guid": "1999002331", "pair_group": "3"},
    "clay slot": {"guid": "100417", "group": "1"},
    "oil slot": {"guid": "100849", "group": "1"},
    "gas slot (arctic)": {"guid": "113750", "group": "1"},
}

TEMPLATE_METADATA = {'clay slot': {'guid': '100417',
                      'source': 'clay oil and gas slots/moderate_c_01_gamedata.xml',
                      'region': 'temperate',
                      'original_id': '-9109656141968703486'},
 'oil slot': {'guid': '100849',
                          'source': 'clay oil and gas slots/moderate_l_01_gamedata.xml',
                          'region': 'temperate',
                          'original_id': '-9192937829875843056'},
 'gas slot (arctic)': {'guid': '113750',
                            'source': 'clay oil and gas slots/colony03_a02_03_gamedata.xml',
                            'region': 'arctic',
                            'original_id': '-9212113033491382240'},
 'Riverslot': {'guid': '117741',
               'source': 'riverslots/colony02_m_04_gamedata.xml',
               'region': 'colony',
               'original_id': '-9209861233677697022'},
 'Riverslot_workarea': {'guid': '1999002331',
                        'source': 'riverslots/colony02_m_04_gamedata.xml',
                        'region': 'colony',
                        'original_id': '-9209861233677697015'}}

TEMPLATE_XML = {'clay slot': '<None>\n'
                     '                    <guid>100417</guid>\n'
                     '                    <ID>-9109656141968703486</ID>\n'
                     '                    <Position>414,5 23,638235 559,5</Position>\n'
                     '                    <Direction>1,5707964</Direction>\n'
                     '                    <ParticipantID>\n'
                     '                      <id>8</id>\n'
                     '                    </ParticipantID>\n'
                     '                    <Blocking />\n'
                     '                    <Building />\n'
                     '                    <QuestObject>\n'
                     '                      <QuestIDs />\n'
                     '                      <ObjectWasVisible>\n'
                     '                        <None>False</None>\n'
                     '                        <None>False</None>\n'
                     '                      </ObjectWasVisible>\n'
                     '                      <OverwriteVisualParticipant />\n'
                     '                    </QuestObject>\n'
                     '                    <Infolayer>\n'
                     '                      <Icons>\n'
                     '                        <None />\n'
                     '                      </Icons>\n'
                     '                    </Infolayer>\n'
                     '                    <Mesh>\n'
                     '                      <Flags>\n'
                     '                        <flags>1</flags>\n'
                     '                      </Flags>\n'
                     '                      <DyeColor>-1</DyeColor>\n'
                     '                      <DyeColorDetail>255 255 255 255</DyeColorDetail>\n'
                     '                      <SequenceData>\n'
                     '                        <CurrentSequenceStartTime>100</CurrentSequenceStartTime>\n'
                     '                      </SequenceData>\n'
                     '                      <Orientation>0 -0,70710677 -0 0,70710677</Orientation>\n'
                     '                    </Mesh>\n'
                     '                    <RandomMapObject />\n'
                     '                    <Selection>\n'
                     '                      <Detected>12336 12336 12336 12336</Detected>\n'
                     '                    </Selection>\n'
                     '                    <SoundEmitter />\n'
                     '                  </None>\n'
                     '                  ',
 'oil slot': '<None>\n'
                         '                    <guid>100849</guid>\n'
                         '                    <ID>-9192937829875843056</ID>\n'
                         '                    <ObjectFolderID>0</ObjectFolderID>\n'
                         '                    <Position>257,5 5,0469193 294,5</Position>\n'
                         '                    <ParticipantID>\n'
                         '                      <id>8</id>\n'
                         '                    </ParticipantID>\n'
                         '                    <Blocking />\n'
                         '                    <Building />\n'
                         '                    <QuestObject>\n'
                         '                      <QuestIDs />\n'
                         '                      <ObjectWasVisible>\n'
                         '                        <None>False</None>\n'
                         '                        <None>False</None>\n'
                         '                      </ObjectWasVisible>\n'
                         '                      <OverwriteVisualParticipant />\n'
                         '                    </QuestObject>\n'
                         '                    <Infolayer>\n'
                         '                      <Icons>\n'
                         '                        <None />\n'
                         '                      </Icons>\n'
                         '                    </Infolayer>\n'
                         '                    <Mesh>\n'
                         '                      <Flags>\n'
                         '                        <flags>1</flags>\n'
                         '                      </Flags>\n'
                         '                      <DyeColor>-1</DyeColor>\n'
                         '                      <SequenceData>\n'
                         '                        <CurrentSequenceStartTime>0</CurrentSequenceStartTime>\n'
                         '                      </SequenceData>\n'
                         '                      <Orientation>0 0 0 1</Orientation>\n'
                         '                    </Mesh>\n'
                         '                    <RandomMapObject />\n'
                         '                    <Selection>\n'
                         '                      <Detected>12336 12336 12336 12336</Detected>\n'
                         '                    </Selection>\n'
                         '                    <SoundEmitter />\n'
                         '                  </None>\n'
                         '                  ',
 'gas slot (arctic)': '<None>\n'
                           '                    <guid>113750</guid>\n'
                           '                    <ID>-9212113033491382240</ID>\n'
                           '                    <ObjectFolderID>0</ObjectFolderID>\n'
                           '                    <Position>131,5 26,117188 156,5</Position>\n'
                           '                    <Direction>4,712389</Direction>\n'
                           '                    <ParticipantID>\n'
                           '                      <id>8</id>\n'
                           '                    </ParticipantID>\n'
                           '                    <Blocking />\n'
                           '                    <Building />\n'
                           '                    <QuestObject>\n'
                           '                      <QuestIDs />\n'
                           '                      <ObjectWasVisible>\n'
                           '                        <None>False</None>\n'
                           '                        <None>False</None>\n'
                           '                      </ObjectWasVisible>\n'
                           '                      <OverwriteVisualParticipant />\n'
                           '                    </QuestObject>\n'
                           '                    <Infolayer>\n'
                           '                      <Icons>\n'
                           '                        <None />\n'
                           '                      </Icons>\n'
                           '                    </Infolayer>\n'
                           '                    <Mesh>\n'
                           '                      <Flags>\n'
                           '                        <flags>1</flags>\n'
                           '                      </Flags>\n'
                           '                      <DyeColor>-1</DyeColor>\n'
                           '                      <DyeColorDetail>255 255 255 255</DyeColorDetail>\n'
                           '                      <SequenceData>\n'
                           '                        <CurrentSequenceID>0</CurrentSequenceID>\n'
                           '                        <CurrentSequenceStartTime>100</CurrentSequenceStartTime>\n'
                           '                        <IdleSequenceID>0</IdleSequenceID>\n'
                           '                      </SequenceData>\n'
                           '                      <Orientation>-6,181724E-08 0,7071068 -6,181724E-08 0,7071068</Orientation>\n'
                           '                    </Mesh>\n'
                           '                    <RandomMapObject />\n'
                           '                    <Selection>\n'
                           '                      <Detected>12336 12336 12336 12336</Detected>\n'
                           '                    </Selection>\n'
                           '                    <SoundEmitter />\n'
                           '                  </None>\n'
                           '                  ',
 'Riverslot': '<None>\n'
              '                    <guid>117741</guid>\n'
              '                    <ID>-9209861233677697022</ID>\n'
              '                    <Variation>1</Variation>\n'
              '                    <ObjectFolderID>2</ObjectFolderID>\n'
              '                    <Position>159,5 1,9979566 165,5</Position>\n'
              '                    <Direction>1,5707964</Direction>\n'
              '                    <ParticipantID>\n'
              '                      <id>8</id>\n'
              '                    </ParticipantID>\n'
              '                    <Blocking />\n'
              '                    <Building />\n'
              '                    <QuestObject>\n'
              '                      <QuestIDs />\n'
              '                      <ObjectWasVisible>\n'
              '                        <None>False</None>\n'
              '                        <None>False</None>\n'
              '                      </ObjectWasVisible>\n'
              '                      <OverwriteVisualParticipant />\n'
              '                    </QuestObject>\n'
              '                    <Infolayer>\n'
              '                      <Icons>\n'
              '                        <None />\n'
              '                      </Icons>\n'
              '                    </Infolayer>\n'
              '                    <Mesh>\n'
              '                      <Flags>\n'
              '                        <flags>1</flags>\n'
              '                      </Flags>\n'
              '                      <DyeColorDetail>255 255 255 255</DyeColorDetail>\n'
              '                      <SequenceData>\n'
              '                        <CurrentSequenceStartTime>0</CurrentSequenceStartTime>\n'
              '                      </SequenceData>\n'
              '                      <Orientation>-0 -0,70710677 -0 0,70710677</Orientation>\n'
              '                    </Mesh>\n'
              '                    <RandomMapObject />\n'
              '                    <Selection>\n'
              '                      <Detected>12336 12336 12336 12336</Detected>\n'
              '                    </Selection>\n'
              '                    <SoundEmitter />\n'
              '                  </None>\n'
              '                  ',
 'Riverslot_workarea': '<None>\n'
                       '                    <guid>1999002331</guid>\n'
                       '                    <ID>-9209861233677697015</ID>\n'
                       '                    <ObjectFolderID>2</ObjectFolderID>\n'
                       '                    <Position>167,5 1,9927818 166,5</Position>\n'
                       '                    <Direction>1,5707964</Direction>\n'
                       '                    <ParticipantID>\n'
                       '                      <id>8</id>\n'
                       '                    </ParticipantID>\n'
                       '                    <Blocking />\n'
                       '                    <Building />\n'
                       '                    <Mesh>\n'
                       '                      <Flags>\n'
                       '                        <flags>1</flags>\n'
                       '                      </Flags>\n'
                       '                      <DyeColorDetail>255 255 255 255</DyeColorDetail>\n'
                       '                      <SequenceData>\n'
                       '                        <CurrentSequenceStartTime>0</CurrentSequenceStartTime>\n'
                       '                      </SequenceData>\n'
                       '                      <Orientation>-0 -0,70710677 -0 0,70710677</Orientation>\n'
                       '                    </Mesh>\n'
                       '                    <Selection>\n'
                       '                      <Detected>12336 12336 12336 12336</Detected>\n'
                       '                    </Selection>\n'
                       '                    <BezierPath>\n'
                       '                      <Path>\n'
                       '                        <TangentScale>0,3</TangentScale>\n'
                       '                        <Minimum>162,54083 2,4706607 166,35333</Minimum>\n'
                       '                        <Maximum>164,86 2,4792495 166,3581</Maximum>\n'
                       '                        <BezierCurve>\n'
                       '                          <None>\n'
                       '                            <p>164,86 2,4706607 166,35333</p>\n'
                       '                            <i>0,6957505 -0,0025766373 -0,0014282227</i>\n'
                       '                            <o>-0,6957505 0,0025766373 0,0014282227</o>\n'
                       '                          </None>\n'
                       '                          <None>\n'
                       '                            <p>162,54083 2,4792495 166,3581</p>\n'
                       '                            <i>0,6957505 -0,0025766373 -0,0014282227</i>\n'
                       '                            <o>-0,6957505 0,0025766373 0,0014282227</o>\n'
                       '                          </None>\n'
                       '                        </BezierCurve>\n'
                       '                      </Path>\n'
                       '                    </BezierPath>\n'
                       '                  </None>\n'
                       '                '}

# Authoritative native deposit templates copied from the working C# Island Editor.
TEMPLATE_XML["clay slot"] = '<None>\n                    <guid>100417</guid>\n                    <ID>-9185091435727159295</ID>\n                    <ObjectFolderID>19</ObjectFolderID>\n                    <Position>267,5 4,4514117 321,5</Position>\n                    <Direction>1,5707964</Direction>\n                    <ParticipantID>\n                      <id>8</id>\n                    </ParticipantID>\n                    <Blocking/>\n                    <Building/>\n                    <QuestObject>\n                      <QuestIDs/>\n                      <ObjectWasVisible>\n                        <None>False</None>\n                        <None>False</None>\n                      </ObjectWasVisible>\n                      <OverwriteVisualParticipant/>\n                    </QuestObject>\n                    <Infolayer>\n                      <Icons>\n                        <None/>\n                      </Icons>\n                    </Infolayer>\n                    <Mesh>\n                      <Flags>\n                        <flags>1</flags>\n                      </Flags>\n                      <SequenceData>\n                        <CurrentSequenceStartTime>100</CurrentSequenceStartTime>\n                      </SequenceData>\n                      <Orientation>0 -0,70710677 -0 0,70710677</Orientation>\n                    </Mesh>\n                    <RandomMapObject/>\n                    <Selection/>\n                    <SoundEmitter>\n                      <TimeBudget>500</TimeBudget>\n                    </SoundEmitter>\n                  </None>'
TEMPLATE_XML["oil slot"] = '<None>\n                    <guid>100849</guid>\n                    <ID>-9191811929969000439</ID>\n                    <ObjectFolderID>20</ObjectFolderID>\n                    <Position>259,5 5,4929047 327,5</Position>\n                    <ParticipantID>\n                      <id>8</id>\n                    </ParticipantID>\n                    <Blocking/>\n                    <Building/>\n                    <QuestObject>\n                      <QuestIDs/>\n                      <ObjectWasVisible>\n                        <None>False</None>\n                        <None>False</None>\n                      </ObjectWasVisible>\n                      <OverwriteVisualParticipant/>\n                    </QuestObject>\n                    <Infolayer>\n                      <Icons>\n                        <None/>\n                      </Icons>\n                    </Infolayer>\n                    <Mesh>\n                      <Flags>\n                        <flags>1</flags>\n                      </Flags>\n                      <SequenceData>\n                        <CurrentSequenceStartTime>100</CurrentSequenceStartTime>\n                      </SequenceData>\n                      <Orientation>0 0 0 1</Orientation>\n                    </Mesh>\n                    <RandomMapObject/>\n                    <Selection/>\n                    <SoundEmitter>\n                      <TimeBudget>500</TimeBudget>\n                    </SoundEmitter>\n                  </None>'
NATIVE_DEPOSIT_SLOT_NAMES = frozenset(("clay slot", "oil slot"))

def template_element(name: str):
    if name not in TEMPLATE_XML:
        raise KeyError(f"Unknown slot template: {name}")
    return copy.deepcopy(ET.fromstring(TEMPLATE_XML[name]))

def river_pair():
    return template_element("Riverslot"), template_element("Riverslot_workarea")
