# %%
import requests
from itertools import zip_longest
from requests.models import HTTPBasicAuth
import numpy as np
import re
import os
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore")
import pandas as pd

# %%
def create_csv(login,password,uuid,lang,sheet):
    #Get access token with a POST request and CMS credentials 
    ext = "https://api-v3.neuro.net/api/v2/ext/auth"
    body = {"username":login,"password":password}
    post = requests.post(ext, auth=HTTPBasicAuth(body["username"],body["password"]))
    try:
        auth_data = post.json()
    except:
        raise Exception("Your email or password were entered incorrectly")
    # %%
    # Request entity data with token and agent uuid
    token = auth_data["token"]
    params = {"agent_uuid":uuid}
    headers = {"Authorization":"Bearer " +token}
    res_ent = requests.get("https://api-v3.neuro.net/api/v2/nlu/entity", params=params, headers=headers)
    res_int = requests.get("https://api-v3.neuro.net/api/v2/nlu/intent", params=params, headers=headers)

    

    # %%
    if(res_ent.status_code == 200 or res_int.status_code == 200):
        print("Request successful")
    else:
        raise AssertionError("Failed to get data. Make sure UUID includes no trailing or following characters")    
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

        # print(plist)
        return plist
    
    
    def split_list_patterns(patterns):
        """Combines every 2 items (pattern, entity_value) in a list """
        args = [iter(patterns)] * 2
        return list(zip_longest(*args))

    def validate_patterns(patterns):
        errors = []
        for p in patterns:
            try:
                re.compile(p[0])
            except re.error:
                errors.append(p)
        
        if errors != []:
            return errors
        

    #Combines the 2 functions above
    split_and_group = lambda x: split_list_patterns(split_raw_patterns(x))
    # %%
    def format_by_lang(df,language):
        """Subsets response data by language and returns a DataFrame with the 
        name of the entity, associated patterns in a list of tuples, and language"""
        try:
            lang_df = df[df["language"]==language].set_index("name")
            lang_df.iloc[0]
            lang_df["pattern"] = lang_df["pattern"].apply(split_and_group)
            return lang_df
        except:
            raise AssertionError("Language \""+language+"\" not found in agent.<br>Please make sure you are using the correct language code and the right agent UUID")

    # %%
    #Setting the df to use for matching
    lang_df = format_by_lang(raw_data,lang)
    validity_df = lang_df.pattern.apply(validate_patterns).dropna().to_frame()
    validity_df.index = validity_df.index.rename("Entity/Intent")

    print(validity_df)
    # print(lang_df.pattern.apply(validate_patterns))
    # %%
    def open_excel():
        """Opens excel sheet and removes empty cells
        returns a DataFrame with the pattern sentences and entity=value"""
        try:
            df = pd.read_excel(sheet, engine="openpyxl",usecols="A,B")
            df.replace(re.compile(".*(null|default).*",flags=re.IGNORECASE),np.nan,regex=True,inplace=True)
            df.dropna(inplace=True)
        
            return df
        except:
            raise AssertionError("Error opening excel sheet")

    def format_test_sheet(sheet,sep="\n"):
        """Creates a new sheet with extra rows from multiple patterns on the same cell 
        in the raw excel sheet"""
        patterns = []
        entities = []
        columns = sheet.columns

        for index, row in sheet.iterrows():
            prompts = row[columns[0]].split("\n")
            for prompt in prompts:
                patterns.append(prompt)
                entities.append(row[columns[1]])

        return pd.DataFrame({"patterns":patterns,"entities":entities})


    def clean_entities(entities):
        """Splits entity column in a list of lists and strips out all unnecessary characters"""
        try:
            split_pattern = re.split("\=\=?", entities)
            plist = list(map(lambda x: re.sub("[\n\r\:\"\=\']","",x),split_pattern))
            return plist
        except:
            raise AssertionError("Pattern sheet not formatted correctly.")

    def clean_patterns(pattern):
        """Removes any non-word characters and spaces from pattern column"""
        try:
            new_pattern = re.sub("[^\w\d\s:]"," ",pattern)
            return new_pattern
        except:
            raise AssertionError("Pattern sheet not formatted correctly")
    # %%
    #Open script excel sheet and save entity and pattern column names
    df_raw = format_test_sheet(open_excel())
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
                try:
                    match = re.search(pattern[0], str_pattern,flags=re.IGNORECASE)
                except:
                    match = None
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
    dir = "output/results.xlsx"
    
    with pd.ExcelWriter(dir) as writer:
        output.to_excel(writer,"Results",encoding='utf-8-sig',index=False,engine="openpyxl")
        validity_df.to_excel(writer,"Errors",encoding='utf-8-sig',index=True,engine="openpyxl")

    return dir
    # return output.to_csv(encoding='utf-8-sig',index=False)