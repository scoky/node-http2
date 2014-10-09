#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')
var http = require('http')
var url = require('url')

var TIMEOUT = 5000 // Give up on requests after 5 secs

// Passing bunyan logger to http2
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
})

// Do not validate server certificate
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"

// Creating an HTTP1.1 server to listen for incoming requests from Awazza
var server = http.createServer(function(request, response) {

  console.log(Date()+" Received request: "+request.url+" "+JSON.stringify(request.headers))

  // Determine upstream server from requested URL
  var poptions = url.parse(request.url)

  // Always send request via HTTP2 over TLS
  poptions.protocol = "https:"
  poptions.port = 443  
  // Convert the http/1.1 headers from Awazza into http/2 headers
  poptions.headers = http2.convertHeadersToH2(request.headers)
  
  // Update the href to reflect the content server
  poptions.host = poptions.hostname = poptions.headers[':authority']
  poptions.href = url.format(poptions)

  // Disable plain text mode
  poptions.plain = false

  // Send the request to the content server
  // console.log("Sending request: "+JSON.stringify(poptions))
  var prequest = http2.request(poptions)
  prequest.on('error', function (err) {
    console.log('PRequest error: '+err)
    // Something went wrong, send Awazza a 502 error
    response.writeHead(502)
    response.end()
  })
  prequest.setTimeout(5000, function () {
    console.log('PRequest timed out')
    // Request timedout
    prequest.abort()
    // Tell Awazza about the timeout
    response.writeHead(504)
    response.end()
  })

  // Receiving the response from content server
  prequest.on('response', function(presponse) {
    presponse.on('error', function(err) {
    console.log('PResponse Error: '+err)
      // Something went wrong, send Awazza a 502 error
      response.writeHead('502')
      response.end()
    })

    console.log(Date()+" Received response: "+request.url+" "+presponse.statusCode+" "+JSON.stringify(presponse.headers))

    response.writeHead(presponse.statusCode, '', http2.convertHeadersFromH2(presponse.headers))
    // Pipe response to Awazza
    presponse.pipe(response)
  })

  prequest.end()
})

/*server.on('error', function(err) { // This will never catch an error?
  console.log('Server error: '+err)
})*/

// Listen on port 2345 by default
server.listen(process.env.HTTP2_PORT || 2345)

