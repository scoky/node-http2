#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var http = require('http')
var url = require('url')
var spawn = require('child_process').spawn

var pre_child = post_child = null

// Creating an HTTP1.1 server to listen for incoming requests from client
var server = http.createServer(function(request, response) {

  console.log(Date()+" Received process restart request")

  // Kill the currently running process
  if (pre_child) {
    console.log(Date()+" Killing former pre process ("+post_child.pid+")")
    pre_child.kill()
  } else {
    create_pre()
  }
  // Kill the currently running process
  if (post_child) {
    console.log(Date()+" Killing former post process ("+post_child.pid+")")
    post_child.kill()
  } else {
    create_post()
  }

  // Restart Awazza
  child = spawn('sudo', ['service', 'awanode', 'restart'])
  child.on('error', on_error)
  child.on('exit', function(code, signal) {
    // Awazza finished restarting, return response to client
    response.writeHead(200)
    response.end()
  })


  var create_pre = function() {
      pre_child = spawn('node', ['pre-awazza-proxy.js'])
      pre_child.on('error', on_error)
      pre_child.on('exit', function(code, signal) {
        create_pre()
      })
      console.log(Date()+" Started pre process ("+pre_child.pid+")")
  }
  var create_post = function() {
      post_child = spawn('node', ['post-awazza-proxy.js'])
      post_child.on('error', on_error)
      post_child.on('exit', function(code, signal) {
        create_post()
      })
      console.log(Date()+" Started post process ("+post_child.pid+")")
  }
  var on_error = function(error) {
    console.error(Date()+' Error running child process: '+error)
  }


  child.stdout.on('data', function(data) {
    console.log(''+data)
  })
  child.stderr.on('data', function(data) {
    console.error(''+data)
  })

  // ERROR HANDLING
  request.on('error', function (err) {
    // Error on request from client
    // Nothing to be done except log the event
    console.log(Date()+' Request error: '+err)
  })
  response.on('error', function (err) {
    // Error sending response to client
    // Nothing to be done except log the event
    console.log(Date()+' Response error: '+err)
  })
})

/*server.on('error', function(err) { // This will never catch an error?
  console.log('Server error: '+err)
})*/

// Listen on port 2345 by default
server.listen(process.env.LIST_PORT || 5678)

