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

// Passing bunyan logger to http2 server
options.log = require('../test/util').createLogger('server');

// Creating HTTP2 server to listen for incoming requests from client
var server = http2.createServer(options, function(request, response) {
  console.log("Received request: "+request);
  var poptions = require('url').parse(request.url);
  // Replace upstream server from URL with Awazza endpoint
  poptions.host = process.env.UP_SERVER || 'localhost'; 
  poptions.port = process.env.UP_PORT || 8899;
  poptions.headers = request.headers;
  // Send HTTP1.1 request to Awazza
  http.get(poptions, function (presponse) {
	// Pipe the response from Awazza to the client
	presponse.pipe(response);
  });
});

server.listen(process.env.HTTP2_PORT || 3456);
