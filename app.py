from flask import Flask, render_template, url_for, request, Response
from patterns import create_csv

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
        return Response(csv,mimetype="text/csv",headers={"Content-disposition":"attachment; filename=results.csv"})
    
    else:
        return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)