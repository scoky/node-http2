#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var http = require('http')
var url = require('url')

// Passing bunyan logger to http2
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
})

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"

// Creating an HTTP1.1 server to listen for incoming requests from Awazza
var server = http.createServer(function(request, response) {
  console.log(Date.now()+" Received request: "+request.url+" "+JSON.stringify(request.headers))

  // Determine upstream server from requested URL
  var poptions = url.parse(request.url);

  // Always send request via HTTP2 over TLS
  poptions.protocol = "https:"
  poptions.port = 443
  poptions.href = url.format(poptions)
  poptions.headers = http2.convertHeadersToH2(request.headers)
  poptions.host = poptions.hostname = poptions.headers[':authority']
  poptions.plain = false

//  console.log("Sending request: "+JSON.stringify(poptions));
  var prequest = http2.request(poptions);
  function onErr(err) {
        console.log('PRequest error: '+err);
        response.writeHead('404');
        response.end();
  };
  prequest.on('error', onErr);

  prequest.setTimeout(5000, function () {
    console.log('PRequest timed out');
    prequest.abort()
    response.writeHead(504)
    response.end()
  })

  // Receiving the response from upstream server
  prequest.on('response', function(presponse) {
        presponse.on('error', function(err) {
          console.log('PResponse Error: '+err);
          response.writeHead('404');
          response.end();
        });
	console.log(Date.now()+" Received response: "+request.url+" "+presponse.statusCode+" "+JSON.stringify(presponse.headers))
        response.writeHead(presponse.statusCode, '', http2.convertHeadersFromH2(presponse.headers))
	// Pipe response to Awazza
       	presponse.pipe(response);
  });

  prequest.end();
});

/*server.on('error', function(err) {
  console.log('Server error: '+err);
});*/

server.listen(process.env.HTTP2_PORT || 2345);

