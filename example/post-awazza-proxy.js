var fs = require('fs');
var path = require('path');
var http2 = require('..');
var http = require("http");

// Passing bunyan logger (optional)
options.log = require('../test/util').createLogger('server');
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
});

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

// Creating the server
var server = http.createServer(function(request, response) {
  var poptions = require('url').parse(request.url);
  var prequest = http2.request(poptions);
  prequest.end();

  // Receiving the response
  request.on('response', function(presponse) {  
	presponse.pipe(response);
  });
});

server.listen(process.env.HTTP2_PORT || 8080);
