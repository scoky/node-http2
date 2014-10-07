#!/usr/bin/env node

var fs = require('fs');
var path = require('path');
var http2 = require('..');
var http = require("http");

//var path_ext = '/h2_awazza'
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
  console.log("Received request: "+request.url+" "+JSON.stringify(request.headers));

  var poptions = require('url').parse(request.url);
  poptions.headers = http2.convertHeadersFromH2(request.headers)

//  poptions.pathname = poptions.pathname.lastIndexOf(path_ext, 0) === 0 ? poptions.pathname.substring(path_ext.length) : poptions.pathname
//  poptions.headers[':path'] = poptions.headers[':path'].lastIndexOf(path_ext, 0) === 0 ? poptions.headers[':path'].substring(path_ext.length) : poptions.headers[':path']

  // Replace upstream server from URL with Awazza endpoint
  poptions.host = poptions.hostname = process.env.UP_SERVER || 'localhost'; 
  poptions.port = process.env.UP_PORT || 8899;
  poptions.protocol = 'http:'
 
  // Send HTTP1.1 request to Awazza
  http.get(poptions, function (presponse) {
    console.log("Received response: "+presponse.statusCode+" "+JSON.stringify(presponse.headers))
    // Convert and write the headers
    response.writeHead(presponse.statusCode, '', http2.convertHeadersToH2(presponse.headers))
    // Pipe the response from Awazza to the client
    presponse.pipe(response);
  });
});

server.listen(process.env.HTTP2_PORT || 4567);
