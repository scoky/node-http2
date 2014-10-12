#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http = require('http')
var url = require('url')
var spawn = require('child_process').spawn

var child = null

// Creating an HTTP1.1 server to listen for incoming requests from client
var server = http.createServer(function(request, response) {

  console.log(Date()+" Received process restart request")

  // Kill the currently running process
  if (child) {
    console.log(Date()+" Killing former process")
    child.stdout.removeAllListeners('data')
    child.stderr.removeAllListeners('data')
    child.kill()
  }

  child = spawn('node', ['post-awazza-proxy.js'])
  child.stdout.on('data', function(data) {
    console.log(''+data)
  })
  child.stderr.on('data', function(data) {
    console.error(''+data)
  })
  child.on('error', function(error) {
    console.error('Error running child process: '+error)
    child = null
  })

  response.writeHead(200)
  response.end()

  // ERROR HANDLING
  request.on('error', function (err) {
    // Error on request from client
    // Nothing to be done except log the event
    console.log('Request error: '+err)
  })
  response.on('error', function (err) {
    // Error sending response to client
    // Nothing to be done except log the event
    console.log('Response error: '+err)
  })
})

/*server.on('error', function(err) { // This will never catch an error?
  console.log('Server error: '+err)
})*/

// Listen on port 2345 by default
server.listen(process.env.HTTP2_PORT || 5678)

