var fs = require('fs');
var path = require('path');
var http2 = require('..');
var http = require("http");

// Passing bunyan logger to http2
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
});

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

// Creating an HTTP1.1 server to listen for incoming requests from Awazza
var server = http.createServer(function(request, response) {
  // Determine upstream server from requested URL
  var poptions = require('url').parse(request.url);

//----------TEMPORARY TESTING--------------
//  poptions.host = "106.186.112.116";
//  poptions.port = 8080;
//----------TEMPORARY TESTING--------------

  // Always send request via HTTP2 over TLS
  poptions.protocol = "https:"
  poptions.port = 443
  var prequest = http2.request(poptions);
  prequest.end();

  // Receiving the response from upstream server
  prequest.on('response', function(presponse) {
	// Pipe response to Awazza  
	presponse.pipe(response);
  });
});

server.listen(process.env.HTTP2_PORT || 2345);
