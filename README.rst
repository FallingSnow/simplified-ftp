==============
simplified-ftp
==============

A class project for CPSC 471 implementing a simplified FTP client and server.


Description
===========

Located in the :code:`src` folder there is a ftp :code:`client` and ftp :code:`server`.

Client
______

The client forms a connection with the server.

Server
______

The server forms a connection with the client.

Dependencies
============

Ensure you have the following dependencies install on your machine before following the setup guide below.

* `Python <https://www.python.org/>`_ 3.7

* `Pipenv <https://pypi.org/project/pipenv/>`_ 2018.11.26


Setup
=====

The commands below show you how to download and setup the project for development.

::

    $ git clone https://github.com/FallingSnow/simplified-ftp.git   # Download source code
    $ cd simplified-ftp                                             # Change directory to downloaded source
    $ pipenv install                                                # Install dependencies

..
Running the Server
==================

::

    $ pipenv run server   # Run server
..
Running the Client
==================

::

    $ pipenv run client   # Run client
..
