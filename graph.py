from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

import pandas as pd
import networkx as nx

import sys

# TODO: will become params
# Fill in with your PAT and org URL
personal_access_token = "<PAT>"
organization_url = "https://dev.azure.com/<org>"

# Create a connection
credentials = BasicAuthentication('', personal_access_token)
connection = Connection(base_url=organization_url, creds=credentials)

process_name = "Agile"
wit_name = "Feature"

client = connection.clients.get_work_item_tracking_process_client()

process_list = client.get_list_of_processes()

process = None

for p in process_list:
    if p.name == process_name:
        process = p
        break

if not process:
    print("No such process found")
    sys.exit(1)

pid = process_type_id
wit_types = client.get_process_work_item_types(pid)

wit_type = None

for t in wit_types:
    if t.name == wit_name:
        wit_type = t
        break

if not wit_type:
    print("No such WIT found")
    sys.exit(1)

# Get Rules

rules = client.get_process_work_item_type_rules(pid, wit_type.reference_name)

cond_df = pd.DataFrame(columns=["rule", "condition_type", "field", "value", "cond_val"])
act_df = pd.DataFrame(columns=["rule", "action_type", "target_field", "value", "act_val"])

# Get conditions and actions fields/values

for rule in rules:
    # Conditions first
    if rule.name == None or rule.is_disabled:
        continue

    df_temp = pd.DataFrame.from_records([cond.as_dict() for cond in rule.conditions]).assign(rule=rule.name)

    if "value" in df_temp.columns:
        df_temp["cond_val"] = df_temp["condition_type"].str.cat(" " + df_temp["value"]. na_rep="")
    else:
        df_temp["cond_val"] = df_temp["condition_type"]

    cond_df = pd.concat([cond_df, df_temp])

    # Then actions

    df_temp = pd.DataFrame.from_records([act.as_dict() for act in rule.actions]).assign(rule=rule.name)
    df_temp["act_val"] = df_temp["action_type"] + ((" " + df_temp["value"]) if "value" in df_temp.columns else "")

    if "value" in df_temp.columns:
        df_temp["act_val"] = df_temp["action_type"].str.cat(" " + df_temp["value"], na_rep="")
    else:
        df_temp["act_val"] = df_temp["action_type"]

    act_df = pd.concat([act_df, df_temp])

cond_df = cond_df.reset_index(drop=True)
act_df = act_df.reset_index(drop=True)

cond_df.to_parquet("cond_df.parquet")
act_df.to_parquet("act_df.parquet")

# Produce graphs

cond_df = cond_df.rename(columns={"cond_val": "label"})
act_df = act_df.rename(columns={"act_val": "label"})

cond_g = nx.from_pandas_edgelist(cond_df, "field", "rule", "label", create_using=nx.MultiDiGraph())
act_g = nx.from_pandas_edgelist(act_df, "rule", "target_field", "label", create_using=nx.MultiDiGraph())

# Combine these

common_g = nx.compose(cond_g, act_g)

common_g = nx.drawing.nx_pydot.to_pydot(common_g)

output = common_g.create_svg()
with open("common.svg", "wb") as f:
    f.write(output)

