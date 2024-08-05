from flask import Flask, render_template, request, send_file
from web3 import Web3
from hexbytes import HexBytes

# import hashlib, json, os, random, string, pathlib
import hashlib, json, os

app = Flask(__name__)
# mod for vercel limit file 1 MB
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024

my_addr = os.getenv("proofdocs_addr")
my_key = os.getenv("proofdocs_key")

provider_url = os.getenv("sepolia_alchemy")
w3 = Web3(Web3.HTTPProvider(provider_url))

contract_addr = os.getenv("proofdocs_contract_addr")
with open("api/contracts/ProofDocs.json") as f:
  info_json = json.load(f)
contract_abi = info_json["abi"]

contract = w3.eth.contract(address=contract_addr, abi=contract_abi)
print(contract)


@app.route("/")
def index():
  return render_template("index.html")


@app.route("/verify")
def verify():
  return render_template("verify.html")


@app.route("/notary")
def notary():
  return render_template("notary.html")


@app.route("/verify_hash", methods=["POST"])
def verify_hash():
  tmp_list = {}
  try:
    file = request.files["file"]
    # delete for vercel that can not save file
    # file.save("check/{}".format(file.filename))
    # readable_hash = hash_file("check/{}".format(file.filename))
    # os.remove("check/{}".format(file.filename))

    # mod for vercel
    readable_hash = hash_file(file)

    result = search_hash(readable_hash)

    tmp_list.clear()
    tmp_list["doc_id"] = result[0]
    tmp_list["hash_value"] = result[1]
    # tmp_list["doc_url"] = result[2]

    tmp_list["tx_hash"] = ""
    tmp_list["tx_fee"] = ""

    if result[1] == "":
      tmp_list["reason"] = result[0]
      tmp_list["doc_id"] = ""
      tmp_list["color"] = "red"
      tmp_list["doc_url"] = ""
      tmp_list["hash_value"] = readable_hash
    else:
      tmp_list[
        "reason"] = "ไฟล์เอกสารอยู่ในระบบ พบค่า Hash ของไฟล์เอกสารที่ตรวจสอบ"
      tmp_list["color"] = "limegreen"
      tmp_list["doc_url"] = result[2]

  except Exception as error:
    tmp_list.clear()
    tmp_list["reason"] = error
    tmp_list["color"] = "red"
    tmp_list["doc_url"] = ""
      
  tmp_list["back_url"] = "verify"

  return render_template("result.html", result=tmp_list)

@app.route("/download/<filename>")
def download(filename):
  path = "upload/" + filename
  # return send_file(path, as_attachment=True)

  isExist = os.path.exists(path)
  if not isExist:
    path = "templates/notfound.html"
  return send_file(path)


def search_hash(file_hash):
  result = ["", "", ""]
  try:
    result = contract.functions.checkDocument(file_hash).call()
  except Exception as error:
    start_pos = str(error).find("Document with this hash doesn't exist")

    if start_pos == -1:
      result[0] = "ตรวจพบข้อผิดพลาด... กรุณาลองใหม่อีกครั้ง"
    else:
      result[0] = "ไม่พบค่า Hash ของไฟล์เอกสารที่ตรวจสอบในระบบ"

    result[1] = ""
    result[2] = ""

  return result


@app.route("/store_hash", methods=["POST"])
def store_hash():
  tmp_list = {}
  try:
    doc_id = request.form["doc_id"]
    file = request.files["file"]

    # file.save("upload/{}".format(file.filename))
    # readable_hash = hash_file("upload/{}".format(file.filename))

    # delete for vercel that can not save file
    # file_ext = pathlib.Path(file.filename).suffix
    # random_name = ''.join(
    #   random.choices(string.ascii_lowercase + string.digits, k=7))
    # fname = "{}{}".format(random_name, file_ext)
    # file.save("upload/{}".format(fname))
    # readable_hash = hash_file("upload/{}".format(fname))

    # mod for vercel
    readable_hash = hash_file(file)
    fname = file.filename

    result = add_new_tx(fname, readable_hash, doc_id)

    tmp_list.clear()
    tmp_list["hash_value"] = readable_hash

    if result[0] != "":
      tmp_list["reason"] = result[0]
      tmp_list["color"] = "red"
      tmp_list["doc_id"] = ""
      tmp_list["doc_url"] = ""
      tmp_list["tx_hash"] = ""
      tmp_list["tx_fee"] = ""
    else:
      tmp_list["reason"] = "นำเข้าไฟล์เอกสาร พร้อมค่า Hash เรียบร้อย"
      tmp_list["color"] = "limegreen"
      tmp_list["doc_id"] = doc_id
      tmp_list["doc_url"] = fname
      tmp_list["tx_hash"] = result[1]
      tmp_list["tx_fee"] = result[2]
  except Exception as error:
    tmp_list.clear()
    tmp_list["reason"] = error
    tmp_list["color"] = "red"
    tmp_list["doc_url"] = ""

  tmp_list["back_url"] = "notary"
  
  return render_template("result.html", result=tmp_list)

def add_new_tx(file_name, hash_value, doc_id):
  result = ["", "", ""]
  try:
    tx = contract.functions.addDocument(doc_id, hash_value,
                                        file_name).build_transaction({
                                          "from":
                                          my_addr,
                                          "nonce":
                                          w3.eth.get_transaction_count(my_addr)
                                        })
    # print(tx)
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=my_key)
    # print(signed_tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    # print(tx_hash)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(tx_receipt)

    gas_price = w3.eth.get_transaction(tx_hash).gasPrice
    gas_used = w3.eth.get_transaction_receipt(tx_hash).gasUsed
    tx_fee = "{:.18f}".format(w3.from_wei((gas_price * gas_used), 'ether'))

    result[0] = ""
    result[1] = HexBytes(tx_hash).hex()
    result[2] = tx_fee

  except Exception as error:
    print(error)
    start_pos = str(error).find("Document with this hash already exists")
    if start_pos == -1:
      result[0] = "ตรวจพบข้อผิดพลาด... กรุณาลองใหม่อีกครั้ง"
    else:
      result[0] = "ไฟล์เอกสารมีการนำเข้าแล้ว พบค่า Hash ของไฟล์เอกสารในระบบ"

  return result


def hash_file(filename):
  # delete for vercel
  # with open(filename, "rb") as f:
  #   bytes = f.read()  # read entire file as bytes
  #   readable_hash = hashlib.sha256(bytes).hexdigest()

  # mod for vercel
  bytes = filename.read()
  readable_hash = hashlib.sha256(bytes).hexdigest()

  return readable_hash


# app.run(host="0.0.0.0", port=81)
