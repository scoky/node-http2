#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
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
// Passing bunyan logger to http2
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
})

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"

var request_count = 0

// Creating HTTP2 server to listen for incoming requests from client
var server = http2.createServer(options, function(request, response) {
  var req_no = request_count++
  console.log((new Date()).toISOString()+" h2-to-h2 request: #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))

  var poptions = url.parse(request.url)
  poptions.headers = http2.convertHeadersToH2(request.headers)
  poptions.servername = poptions.host = poptions.hostname = 'localhost'//poptions.headers[':authority']
  poptions.protocol = 'https:'
  poptions.slashes = true
  // Server port number
  poptions.port = process.env.UP_PORT || 6789
  poptions.href = poptions.url = url.format(poptions)
  poptions.plain = false
 
  // Send the request to the content server
  console.log((new Date()).toISOString()+" h2-to-h2 request: #"+req_no+"# "+JSON.stringify(poptions))

  var prequest = http2.request(poptions)
  // Receiving the response from content server
  prequest.on('response', function(presponse) {  
    console.log((new Date()).toISOString()+" h2-to-h2 response: #"+req_no+"# "+presponse.statusCode+" "+JSON.stringify(presponse.headers))

    response.writeHead(presponse.statusCode, '', http2.convertHeadersToH2(presponse.headers))
    // Pipe response to Awazza
    presponse.pipe(response)

    presponse.on('error', function(err) {
      console.log((new Date()).toISOString()+' PResponse Error: '+err)
      // Send back an error
      response.writeHead(502)
      response.end()
    })
  })

  if (poptions.headers['content-length'] > 0) {
    request.pipe(prequest)
  } else {
    prequest.end()
  }

  // ERROR HANDLING
  request.on('error', function (err) {
    // Error on request from client
    // Nothing to be done except log the event
    console.log((new Date()).toISOString()+' Request Error: '+err)
  })
  response.on('error', function (err) {
    // Error sending response to client
    // Nothing to be done except log the event
    console.log((new Date()).toISOString()+' Response Error: '+err)
  })
  prequest.on('error', function (err) {
    // Return an error to the client
    console.log((new Date()).toISOString()+' PRequest Error: '+err)
    response.writeHead(502)
    response.end()
  })
})

// Listen on port 4567 by default
server.listen(process.env.PROXY_PORT || 4567)
