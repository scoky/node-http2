#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var http = require("http")
var crypto = require('crypto');
var url = require('url')

var options = process.env.HTTP2_PLAIN ? {
  plain: true
} : {
  // Dub certificate to issue to clients
  key: fs.readFileSync(path.join(__dirname, '/localhost.key')),
  cert: fs.readFileSync(path.join(__dirname, '/localhost.crt'))
}

// Passing bunyan logger to http2 server
options.log = require('../test/util').createLogger('server')

// To get servername from TLS handshake
// Could use to parallelize post- TLS handshake
// Unfortunately, the 'servername' is the proxy, not the content server
/*options.SNICallback = function (servername) {
  console.log('Incoming TLS session for '+servername)
  var details = {
    key: options.key,
    cert: options.cert
  }
  return crypto.createCredentials(details).context
}*/

var request_count = 0

// Creating HTTP2 server to listen for incoming requests from client
var server = http2.createServer(options, function(request, response) {
  var req_no = request_count++
  console.log(Date()+" Received request: #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))

  var poptions = url.parse(request.url)
  // Convert the http/2 headers received from the client into http/1.1 headers for Awazza
  poptions.headers = http2.convertHeadersFromH2(request.headers)
  poptions.host = poptions.hostname = poptions.headers.host
  poptions.href = poptions.url = url.format(poptions)

  // Replace upstream server from URL with Awazza endpoint, default localhost:8899
  poptions.host = poptions.hostname = process.env.UP_SERVER || 'localhost'
  poptions.port = process.env.UP_PORT || 8899
  // Awazza doesn't speak https
  poptions.protocol = 'http:'
 
  // Send http/1.1 request to Awazza
  var prequest = http.request(poptions, function (presponse) {

    console.log(Date()+" Received response: #"+req_no+"# "+presponse.statusCode+" "+JSON.stringify(presponse.headers))

    // Convert and write the headers
    response.writeHead(presponse.statusCode, '', http2.convertHeadersToH2(presponse.headers))
    // Pipe the response from Awazza to the client
    presponse.pipe(response)

    presponse.on('error', function (err) {
      // Return an error to the client
      console.log('PResponse Error: '+err)
      response.writeHeader(502)
      response.end()
    })
  })

  if (poptions.headers['content-length'] > 0) {
    request.pipe(prequest)
  }
  prequest.end()

  // ERROR HANDLING
  request.on('error', function (err) {
    // Error on request from client
    // Nothing to be done except log the event
    console.log('Request Error: '+err)
  })
  response.on('error', function (err) {
    // Error sending response to client
    // Nothing to be done except log the event
    console.log('Response Error: '+err)
  })
  prequest.on('error', function (err) {
    // Return an error to the client
    console.log('PRequest Error: '+err)
    response.writeHead(502)
    response.end()
  })
})

// Listen on port 4567 by default
server.listen(process.env.HTTP2_PORT || 4567)
