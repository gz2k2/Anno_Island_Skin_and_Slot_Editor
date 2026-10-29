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
MINE_WORKAREA_GUID = "1000253"
MINE_SLOT_GUIDS = frozenset(("1000029", "614", "116037"))
MINE_WORKAREA_GROUP = "3"
MINE_PRIMARY_GROUP = "1"
MINE_MIN_DISTANCE = 2.0
MINE_MAX_DISTANCE = 64.0
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

# Authoritative Mine/Work Area templates copied verbatim from the working C# Island Editor.
MINE_TEMPLATE_NAME = "MineSlot_native"
MINE_WORKAREA_TEMPLATE_NAME = "MineSlot_workarea_native"
TEMPLATE_XML[MINE_TEMPLATE_NAME] = '<None>\n                    <guid>1000029</guid>\n                    <ID>-9199693229316898762</ID>\n                    <ObjectFolderID>6</ObjectFolderID>\n                    <Position>234,5 6,253151 201,5</Position>\n                    <ParticipantID>\n                      <id>8</id>\n                    </ParticipantID>\n                    <Blocking />\n                    <Building />\n                    <QuestObject>\n                      <QuestIDs />\n                      <ObjectWasVisible>\n                        <None>False</None>\n                        <None>False</None>\n                      </ObjectWasVisible>\n                      <OverwriteVisualParticipant />\n                    </QuestObject>\n                    <Infolayer>\n                      <Icons />\n                    </Infolayer>\n                    <Mesh>\n                      <Flags>\n                        <flags>1</flags>\n                      </Flags>\n                      <SequenceData>\n                        <CurrentSequenceID>1000</CurrentSequenceID>\n                        <CurrentSequenceStartTime>157800</CurrentSequenceStartTime>\n                        <IdleSequenceID>1000</IdleSequenceID>\n                      </SequenceData>\n                      <Orientation>0 0 0 1</Orientation>\n                    </Mesh>\n                    <RandomMapObject />\n                    <Selection />\n                    <SoundEmitter>\n                      <TimeBudget>500</TimeBudget>\n                    </SoundEmitter>\n                  </None>'
TEMPLATE_XML[MINE_WORKAREA_TEMPLATE_NAME] = '<None>\n                    <guid>1000253</guid>\n                    <ID>-9199693229316898788</ID>\n                    <ObjectFolderID>5</ObjectFolderID>\n                    <Position>249,22966 11,178814 207,56378</Position>\n                    <Direction>2,617489</Direction>\n                    <ParticipantID>\n                      <id>8</id>\n                    </ParticipantID>\n                    <Building />\n                    <Mesh>\n                      <Flags>\n                        <flags>1</flags>\n                      </Flags>\n                      <SequenceData>\n                        <CurrentSequenceID>1000</CurrentSequenceID>\n                        <CurrentSequenceStartTime>157800</CurrentSequenceStartTime>\n                        <IdleSequenceID>1000</IdleSequenceID>\n                      </SequenceData>\n                      <Orientation>0 -0,9658605 -0 0,25906283</Orientation>\n                    </Mesh>\n                    <RandomMapObject />\n                    <Selection />\n                    <BezierPath>\n                      <Path>\n                        <TangentScale>0,3</TangentScale>\n                        <Minimum>244,5 4,7158194 207,25558</Minimum>\n                        <Maximum>249,76285 11,362601 219</Maximum>\n                        <BezierCurve>\n                          <None>\n                            <p>249,76285 11,362601 207,25558</p>\n                            <i>0,3464905 0,05647545 -0,20601197</i>\n                            <o>-0,3464905 -0,05647545 0,20601197</o>\n                          </None>\n                          <None>\n                            <p>248,60788 11,17435 207,94229</p>\n                            <i>0,34110728 0,111504905 -0,19208993</i>\n                            <o>-0,3626191 -0,11853693 0,20420402</o>\n                          </None>\n                          <None>\n                            <p>247,43874 10,60287 208,56438</p>\n                            <i>0,36206326 0,19841103 -0,12956148</i>\n                            <o>-0,453072 -0,24828394 0,16212825</o>\n                          </None>\n                          <None>\n                            <p>245,91458 9,69842 208,90607</p>\n                            <i>0,39103687 0,27731124 -0,25178042</i>\n                            <o>-0,43130556 -0,30586854 0,27770856</o>\n                          </None>\n                          <None>\n                            <p>244,81053 8,739029 210,25662</p>\n                            <i>0,063565366 0,3160513 -0,5027654</i>\n                            <o>-0,10288367 -0,5115446 0,8137505</o>\n                          </None>\n                          <None>\n                            <p>245,39857 7,1328 212,98738</p>\n                            <i>0,03284875 0,47718197 -0,8400424</i>\n                            <o>-0,033156924 -0,4816587 0,84792334</o>\n                          </None>\n                          <None>\n                            <p>244,59567 5,6178493 215,75122</p>\n                            <i>0,15319547 0,38853776 -0,88183784</i>\n                            <o>-0,10367764 -0,26294953 0,5967987</o>\n                          </None>\n                          <None>\n                            <p>244,5522 4,986206 217,85936</p>\n                            <i>0,018730085 0,17659286 -0,6360223</i>\n                            <o>-0,00998477 -0,0941394 0,33905536</o>\n                          </None>\n                          <None>\n                            <p>244,5 4,7158194 219</p>\n                            <i>0,015660096 0,08111601 -0,34219208</i>\n                            <o>-0,015660096 -0,08111601 0,34219208</o>\n                          </None>\n                        </BezierCurve>\n                      </Path>\n                    </BezierPath>\n                  </None>'

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
