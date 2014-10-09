#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var http = require("http")

var options = process.env.HTTP2_PLAIN ? {
  plain: true
} : {
  // Dub certificate to issue to clients
  key: fs.readFileSync(path.join(__dirname, '/localhost.key')),
  cert: fs.readFileSync(path.join(__dirname, '/localhost.crt'))
}

// Passing bunyan logger to http2 server
options.log = require('../test/util').createLogger('server')

// Creating HTTP2 server to listen for incoming requests from client
var server = http2.createServer(options, function(request, response) {

  console.log(Date()+" Received request: "+request.url+" "+JSON.stringify(request.headers))

  var poptions = require('url').parse(request.url)
  // Convert the http/2 headers received from the client into http/1.1 headers for Awazza
  poptions.headers = http2.convertHeadersFromH2(request.headers)

  // Replace upstream server from URL with Awazza endpoint, default localhost:8899
  poptions.host = poptions.hostname = process.env.UP_SERVER || 'localhost'
  poptions.port = process.env.UP_PORT || 8899
  // Awazza doesn't speak https
  poptions.protocol = 'http:'
 
  // Send http/1.1 request to Awazza
  http.get(poptions, function (presponse) {

    console.log(Date()+" Received response: "+request.url+' '+presponse.statusCode+" "+JSON.stringify(presponse.headers))

    // Convert and write the headers
    response.writeHead(presponse.statusCode, '', http2.convertHeadersToH2(presponse.headers))
    // Pipe the response from Awazza to the client
    presponse.pipe(response)
  })

  response.on('error', function (err) {
    // Error sending response to client
    // Nothing to be done except log the event
    console.log('Response Error: '+err)
  })
})

// Listen on port 4567 by default
server.listen(process.env.HTTP2_PORT || 4567)
