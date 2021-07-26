# %%
import requests
from itertools import zip_longest
from requests.models import HTTPBasicAuth
import numpy as np
import pandas as pd
import re
# %%
#Get access token with a POST request and CMS credentials 
def authenticate(username,password):
    ext = "https://api-v3.neuro.net/api/v2/ext/auth"
    body = {"username":username,"password":password}
    post = requests.post(ext, auth=HTTPBasicAuth(body["username"],body["password"]))
    auth_data = post.json()
    return auth_data
# %%
def get_data(username,password,uuid):
    # Request entity data with token and agent uuid
    token = authenticate(username,password)["token"]
    params = {"agent_uuid":uuid}
    headers = {"Authorization":"Bearer " +token}
    #TODO: get intents as well
    res = requests.get("https://api-v3.neuro.net/api/v2/nlu/entity", params=params,headers=headers)
    # status = "successful" if res.status_code == 200 else "failed"
    if(res.status_code == 200):
        print("Request successful")
        return res
    else:
        raise AssertionError("Failed to get data")
# %%
def split_raw_patterns(patterns):
    """Splits raw patterns into separate patterns and entity values"""
    plist = re.split("(\"[A-Za-z0-9_]{1,25}\")",patterns)
    plist = list(map(lambda x: re.sub("[\n\r\:\"]","",x),plist))
    plist = list(map(lambda x: x.strip(),plist))
    if(plist[-1]==""):
        plist.pop()
    
    return plist

def split_list_patterns(patterns):
    """Combines every 2 items (pattern, entity_value) in a list """
    args = [iter(patterns)] * 2
    return list(zip_longest(*args))

#Combines the 2 functions above
split_and_group = lambda x: split_list_patterns(split_raw_patterns(x))

# %%
# %%
def clean_data(username,password,uuid,lang):
    """Subsets response data by language and returns a DataFrame with the 
    name of the entity, associated patterns in a list of tuples, and language"""
    #Extract relevant data out of the response json
    relevant_columns = ["name","pattern","language"]
    df = pd.DataFrame(get_data(username,password,uuid).json()["data"],columns=relevant_columns)
    try:
        lang_df = df[df["language"]==lang].set_index("name")
        lang_df["pattern"] = lang_df["pattern"].apply(split_and_group)
        return lang_df
    except:
        raise AssertionError("Language \""+lang+"\" not found in agent")

# %%
def clean_entities(entities):
    """Splits entity column in a list of lists and strips out all unnecessary characters"""
    split_pattern = re.split("\=\=?", entities)
    plist = list(map(lambda x: re.sub("[\n\r\:\"\=]","",x),split_pattern))
    return plist

def clean_patterns(pattern):
    """Removes any non-word characters and spaces from pattern column"""
    new_pattern = re.sub("[^\w\d\s:]"," ",pattern)
    return new_pattern
# %%
#Open script excel sheet and save entity and pattern column names
def open_excel(sheet):
    """Opens excel sheet and removes empty cells
    returns a DataFrame with the pattern sentences and entity=value"""
    df = pd.read_excel(sheet, engine="openpyxl")
    df.replace(re.compile(".*(null|default).*",flags=re.IGNORECASE),np.nan,regex=True,inplace=True)
    df.dropna(inplace=True)
    
    try:
        # Cleaning pattern and entity columns
        entity_col = df.columns[-1]
        pattern_col = df.columns[0]

        df[pattern_col] = df[pattern_col].apply(clean_patterns)
        df[entity_col] = df[entity_col].apply(clean_entities)

        #Split entity column into separate entity and value columns
        df["entities_"] = df[entity_col].map(lambda x: x[0])
        df["values_"] = df[entity_col].map(lambda x: x[1])

        return {"df":df,"pattern_col":pattern_col,"entity_col":entity_col}
    except:
        raise AssertionError("Pattern sheet not formatted correctly")
# %%
def match_patterns(str_pattern,username,password,uuid,lang):
    """Returns a list of all matched entities for every script pattern"""
    search = []
    lang_df=clean_data(username,password,uuid,lang)
    for name in lang_df.index:
        for pattern in lang_df.loc[name]["pattern"]:
            match = re.search(pattern[0], str_pattern,flags=re.IGNORECASE)
            if(match!=None):
                search.append([pattern[0],name+"="+str(pattern[1])])
                break
    
    matches = list(filter(lambda x: x[1]!=None,search))
    return matches
# %%
def make_matches(username,password,uuid,lang,sheet):
    #Create a "matches" column for the DataFrame from the script sheet
    df_raw = open_excel(sheet)
    df = df_raw["df"]
    patt = df_raw["pattern_col"]
    ent = df_raw["entity_col"]

    df["matches"]= df[patt].apply(match_patterns,args=(username,password,uuid,lang))
    output = df[[patt]]

    #Joins the [entity, value] lists in a single string entity=value 
    join_entities = lambda x: "=".join(x)   
    output["entity"] = df[ent].apply(join_entities)
    output["matches"] = df["matches"]

    return output

# %%
#Create a list of match outcomes and add it to the output DataFrame
def create_csv(username,password,uuid,lang,sheet):
    output = make_matches(username,password,uuid,lang,sheet)
    success = []
    for i in range(len(output)):
        matched = False
        for m in output.iloc[i].matches:
            if(m[1]==output.iloc[i].entity or m[1][1]== output.iloc[i].entity):
                matched = True

        success.append(matched)

    output["matched"]=success

    #Output the DataFrame as a string csv with encoding utf-8 signed for Arabic
    return output.to_csv(encoding='utf-8-sig',index=False)