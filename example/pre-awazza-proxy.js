var fs = require('fs');
var path = require('path');
var http2 = require('..');
var http = require("http");

var options = process.env.HTTP2_PLAIN ? {
  plain: true
} : {
  key: fs.readFileSync(path.join(__dirname, '/localhost.key')),
  cert: fs.readFileSync(path.join(__dirname, '/localhost.crt'))
};

// Passing bunyan logger (optional)
options.log = require('../test/util').createLogger('server');
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
});

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

// Creating the server
var server = http2.createServer(options, function(request, response) {
  var poptions = require('url').parse(request.url);
  poptions.host = process.env.UP_SERVER; // Location of upstream server, either awazza testing proxy or webserver
  poptions.port = process.env.UP_PORT;
  // HOST header should be taken care of by the final client
  http.get(poptions, function (presponse) {
	presponse.pipe(response);
  });
});

server.listen(process.env.HTTP2_PORT || 8080);
