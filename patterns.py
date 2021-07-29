# %%
import requests
from itertools import zip_longest
from requests.models import HTTPBasicAuth
import numpy as np
import pandas as pd
import re
import os
# %%
def create_csv(login,password,uuid,lang,sheet):
    #Get access token with a POST request and CMS credentials 
    ext = "https://api-v3.neuro.net/api/v2/ext/auth"
    body = {"username":login,"password":password}
    post = requests.post(ext, auth=HTTPBasicAuth(body["username"],body["password"]))
    auth_data = post.json()
    # %%
    # Request entity data with token and agent uuid
    token = auth_data["token"]
    params = {"agent_uuid":uuid}
    headers = {"Authorization":"Bearer " +token}
    res_ent = requests.get("https://api-v3.neuro.net/api/v2/nlu/entity", params=params, headers=headers)
    res_int = requests.get("https://api-v3.neuro.net/api/v2/nlu/intent", params=params, headers=headers)

    # %%
    status = "successful" if (res_ent.status_code == 200 and res_int.status_code == 200) else "failed"
    print("Request "+status)
    # %%
    #Extract relevant data out of the response json
    relevant_columns = ["name","pattern","language"]
    raw_ent = pd.DataFrame(res_ent.json()["data"],columns=relevant_columns)
    raw_int = pd.DataFrame(res_int.json()["data"],columns=relevant_columns)
    raw_data = pd.concat((raw_ent,raw_int))
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
    def format_by_lang(df,language):
        """Subsets response data by language and returns a DataFrame with the 
        name of the entity, associated patterns in a list of tuples, and language"""
        lang_df = df[df["language"]==language].set_index("name")
        lang_df["pattern"] = lang_df["pattern"].apply(split_and_group)
        return lang_df

    # %%
    #Setting the df to use for matching
    lang_df = format_by_lang(raw_data,lang)
    # %%
    def open_excel():
        """Opens excel sheet and removes empty cells
        returns a DataFrame with the pattern sentences and entity=value"""
    
        df = pd.read_excel(sheet, engine="openpyxl")
        df.replace(re.compile(".*(null|default).*",flags=re.IGNORECASE),np.nan,regex=True,inplace=True)
        df.dropna(inplace=True)
        # print(df)
        return df

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
    df_raw = open_excel()
    entity_col = df_raw.columns[-1]
    pattern_col = df_raw.columns[0]
    # %%
    # Cleaning pattern and entity columns
    df_raw[pattern_col] = df_raw[pattern_col].apply(clean_patterns)
    df_raw[entity_col] = df_raw[entity_col].apply(clean_entities)
    # %%
    #Split entity column into separate entity and value columns
    df_raw["entities_"] = df_raw[entity_col].map(lambda x: x[0])
    df_raw["values_"] = df_raw[entity_col].map(lambda x: x[1])
    # %%

    def match_patterns(str_pattern):
        """Returns a list of all matched entities for every script pattern"""
        search = []

        for name in lang_df.index:
            for pattern in lang_df.loc[name]["pattern"]:
                match = re.search(pattern[0], str_pattern,flags=re.IGNORECASE)
                if(match!=None):
                    search.append([pattern[0],name+"="+str(pattern[1])])
                    break
        
        matches = list(filter(lambda x: x[1]!=None,search))
        return matches
    # %%
    #Create a "matches" column for the DataFrame from the script sheet
    df_raw["matches"]= df_raw[pattern_col].apply(match_patterns)
    output = df_raw[[pattern_col]]

    #Joins the [entity, value] lists in a single string entity=value 
    join_entities = lambda x: "=".join(x)   
    output["entity"] = df_raw[entity_col].apply(join_entities)
    output["matches"] = df_raw["matches"]

    # %%
    #Create a list of match outcomes and add it to the output DataFrame
    success = []
    for i in range(len(output)):
        matched = False
        for m in output.iloc[i].matches:
            if(m[1]==output.iloc[i].entity or m[1][1]== output.iloc[i].entity):
                matched = True

        success.append(matched)

    output["result"]=success
    # %%
    #Output the DataFrame to a csv with encoding utf-8 signed for Arabic
    return output.to_csv(encoding='utf-8-sig',index=False)