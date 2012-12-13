from django.http import HttpResponse
from error.models import Error

from app.utils import render_plain
from app.utils import render_html
from receiving.post import populate

def post(request):
    """ Add in a post """
    err = Error()
    err.ip = request.META.get("REMOTE_ADDR", "")
    err.user_agent = request.META.get("HTTP_USER_AGENT", "")

    populate(err, request.POST)
    return render_plain("Error recorded")

def get(request):
    html = """<html>
<head>
<script src="http://error-collector.appspot.com/lib/error.js"></script>
<script>
arecibo.account = 'fa4c2d457f31697dc41dfeec13e6f468';
window.addEventListener("message", function receiveMessage(event) {
var data = event.data;
arecibo.msg = data.url + " at line " + data.line + ": " + data.msg;
arecibo.traceback = data.stack; // NOTE: This will only be available on Firefox
arecibo.url = data.url;
arecibo.type = data.type;
arecibo.username = data.username;
arecibo.server = data.server;
arecibo.uid = data.uid;
arecibo.ajaxPostLoad();
}, false); 
</script>
</head>
<body></body>
</html>"""
    return render_html(html)
