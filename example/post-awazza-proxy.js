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
var request_count = 0

// Creating an HTTP1.1 server to listen for incoming requests from Awazza
var server = http.createServer(function(request, response) {
  var req_no = request_count++
  console.log(Date().toISOString()+" Post received request: #"+req_no+"# "+request.url+" "+JSON.stringify(request.headers))

  // Determine upstream server from requested URL
  var poptions = url.parse(request.url)

  // Always send request via HTTP2 over TLS
  poptions.protocol = "https:"
  poptions.port = 443  
  // Convert the http/1.1 headers from Awazza into http/2 headers
  poptions.headers = http2.convertHeadersToH2(request.headers)
  
  // Update the href to reflect the content server
  poptions.servername = poptions.host = poptions.hostname = poptions.headers[':authority']
  poptions.href = poptions.url = url.format(poptions)

  // Disable plain text mode
  poptions.plain = false

  // Send the request to the content server
  //console.log("Sending request: "+JSON.stringify(poptions))
  var prequest = http2.request(poptions)
  // Receiving the response from content server
  prequest.on('response', function(presponse) {  

    console.log(Date().toISOString()+" Post received response: #"+req_no+"# "+presponse.statusCode+" "+JSON.stringify(presponse.headers))
    var rheaders = http2.convertHeadersFromH2(presponse.headers)
    // Response contains a location. Convert the location to http: for Awazza
    if (rheaders.location) {
      var location = url.parse(url.resolve(poptions.url, rheaders.location))
      location.protocol = 'http:'
      rheaders.location = url.format(location)
    }

    response.writeHead(presponse.statusCode, '', rheaders)
    // Pipe response to Awazza
    presponse.pipe(response)

    presponse.on('error', function(err) {
      console.log(Date().toISOString()+' PResponse Error: '+err)
      // Something went wrong, send Awazza a 502 error
      response.writeHead(502)
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
    console.log(Date().toISOString()+' Request error: '+err)
  })
  response.on('error', function (err) {
    // Error sending response to client
    // Nothing to be done except log the event
    console.log(Date().toISOString()+' Response error: '+err)
  })
  prequest.on('error', function (err) {
    console.log(Date().toISOString()+' PRequest error: '+err)
    // Something went wrong during request to content server
    // Send Awazza a 502 error
    response.writeHead(502)
    response.end()
  })
  // Timeout only applied to HTTP session, not TCP connect
  /*prequest.setTimeout(5000, function () {
    console.log('PRequest timed out')
    // Request timedout to content server
    prequest.abort()
    // Tell Awazza about the timeout
    response.writeHead(504)
    response.end()
  })*/
})

/*server.on('error', function(err) { // This will never catch an error?
  console.log('Server error: '+err)
})*/

// Listen on port 2345 by default
server.listen(process.env.POST_PORT || 2345)

