from flask import Flask, render_template, url_for, request, Response, make_response, send_file
from patterns import create_csv
import codecs
import pandas as pd
import os

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "/uploads"

@app.route("/", methods=["POST","GET"])
def index():
    errors = ""
    if(request.method == "POST"):
        login = request.form["login"]
        password = request.form["password"]
        uuid = request.form["uuid"]
        lang = request.form["lang"]
        sheet = request.files["sheet"]

        try:
            dir = create_csv(login,password,uuid,lang,sheet)
            #Encoding csv file with utf_8_sig for Arabic, Vietnamese, etc..
            # res = Response(csv.encode("utf-8-sig"),mimetype="text/csv;charset=UTF-8",headers={"Content-disposition":"attachment; filename=results.csv"})
            res = send_file(dir)
        except Exception as e:
            res = str(e)

        # print(res)
        
        return res;
        
    
    else:
        return render_template("index.html",errors="")

if __name__ == "__main__":
    app.run(debug=True)