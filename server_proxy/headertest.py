from email.parser import HeaderParser
request_text = """asdfaklsdfasdf
asdasdfas: asdfasef
qwefqwefq: egrwergw"""
header_portion = "\n".join(request_text.splitlines()[1:])
headers = HeaderParser().parsestr(header_portion)
print(headers.get("asdfas","blahblah"))