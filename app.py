from flask import Flask, render_template, url_for, request, Response, make_response
from patterns import create_csv
import codecs
import pandas as pd

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "/uploads"

@app.route("/", methods=["POST","GET"])
def index():
    if(request.method == "POST"):
        login = request.form["login"]
        password = request.form["password"]
        uuid = request.form["uuid"]
        lang = request.form["lang"]
        sheet = request.files["sheet"]
        
        csv = create_csv(login,password,uuid,lang,sheet)

        #Encoding with utf_8_sig for Arabic, Vietnamese, etc..
        res = Response(csv.encode("utf-8-sig"),mimetype="text/csv;charset=UTF-8",headers={"Content-disposition":"attachment; filename=results.csv"})

        return res;
    
    else:
        return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)