
main_dir =r"C:\Users\aashraf\Desktop"
db_dir = r"C:/Users/aashraf/Desktop"


# ======================================================= WA Setup ===================================================

wa_verify_token = "Sana"
phone_number_id = "209325405605976"
access_token = "EAARxAciB8DkBOZCGaSgDvSdAJZCPAI5EDmo37jWSW6ZCDqQK2jnbo1IYClZCkNjBoA4aPZCniwr5vukfohkUSID1DBBJ6NbwfwKw7rZBWwPclPuHZCHUbxcVmaEOZBMaD2sf8caCufs3pOMlHHHAFgiePp5NAoT0MjTGMo2GziA2kk1gBPKb2pxdsIfNdZATaRxOdbTG35qUjDJ4XZBjHL"
wa_base_url = "https://graph.facebook.com/v19.0/" + phone_number_id
wa_request_url = wa_base_url + "/messages"
wa_media_url = wa_base_url + "/media"
wa_local_files_repo = r"{0}\Test_Folder".format(main_dir)


# ======================================================= XCally Setup ================================================

xcally_channel_key = "Sana"
xcally_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjI1MzQwMjMwMDgwMCwibm9uY2UiOiIyN2E4OTI4MDdjYzY5NDBiODYxN2Y3NTZkYjFlNGY5OSIsInN1YiI6MSwiaXNzIjoiY2MyY2RmMTktMjYzMi05N2FhLWI2Y2EtYWJiMDczMjJhZWY2IiwiYXVkIjoiMzM2MmNlYTAxNTg0YWY2Yjk0ZDk0YzgwZTA3YTBjODZiYTkzODU2MDk4OWIwYzgwN2UzYmY0Yjk1Nzk2YTBjZTRiMWQ4ODBkMjRmZWYwMTY0MDY3MzhkZGU2YzQzZDJjMjU2ZWJiZTgwZDMxMDIzODkyNjkwMTI1N2VjYWJjZjYiLCIzMzYyY2VhMDE1ODRhZjZiOTRkOTRjODBlMDdhMGM4NmJhOTM4NTYwOTg5YjBjODA3ZTNiZjRiOTU3OTZhMGNlNGIxZDg4MGQyNGZlZjAxNjQwNjczOGRkZTZjNDNkMmMyNTZlYmJlODBkMzEwMjM4OTI2OTAxMjU3ZWNhYmNmNiI6bnVsbH0.u7N-axzujAQTbs-5VwBUmoQguQx7IveKETdkq9Gbor4"
xcally_open_channel_id = "5"
xcally_base_url = "https://xcally.sanasofteg.com/api"
xcally_create_msg_url = xcally_base_url+"/openchannel/accounts/"+xcally_open_channel_id+"/notify?apikey="+xcally_api_key
xcally_local_files_repo = r"{0}\Test_Folder".format(main_dir)

# ======================================================= Logs Setup ================================================

meta_xcally_logs_dir_path = r'{0}\WA_XC_Logs'.format(main_dir)
xcally_logs_path = r"{0}\WA_XC_Logs\XC_Errors.log".format(main_dir)
wa_logs_path = r'{0}\WA_XC_Logs\WA_Errors.log'.format(main_dir)


# ======================================================= DB Setup ================================================

# db_path = 'sqlite:///{0}/failed_tasks_db.db'.format(db_dir)
db_path = 'postgresql://postgres:pass123@localhost:5432/postgres' # postgresql:// {user}:{password}@{host}:{port}/{database}