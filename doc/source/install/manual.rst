..
    Copyright 2014 Mirantis, Inc.

    Licensed under the Apache License, Version 2.0 (the "License"); you may
    not use this file except in compliance with the License. You may obtain
    a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
    License for the specific language governing permissions and limitations
    under the License.
..

.. _installing_manually:

===============================
Installing and Running Manually
===============================

Prepare Environment
===================

Install Prerequisites
---------------------

First you need to install a number of packages with your OS package manager.
The list of packages depends on the OS you use.

Ubuntu
^^^^^^

.. code-block:: console

    $ sudo apt-get install python-pip python-dev \
    > libmysqlclient-dev libpq-dev \
    > libxml2-dev libxslt1-dev \
    > libffi-dev
..

Fedora
^^^^^^

.. note::

    Fedora support wasn't thoroughly tested. We do not guarantee that Murano
    will work on Fedora.
..

.. code-block:: console

    $ sudo yum install gcc python-setuptools python-devel python-pip
..


CentOS
^^^^^^

.. code-block:: console

    $ sudo yum install gcc python-setuptools python-devel
    $ sudo easy_install pip
..


Install tox
-----------

.. code-block:: console

    $ sudo pip install tox
..


Install And Configure Database
------------------------------

Murano can use various database types on backend. For development purposes
SQLite is enough in most cases. For production installations you should use
MySQL or PostgreSQL databases.

.. warning::

    Although Murano could use PostgreSQL database on backend, it wasn't
    thoroughly tested and should be used with caution.
..

To use MySQL database you should install it and create an empty database first:

.. code-block:: console

    $ apt-get install python-mysqldb mysql-server
..

.. code-block:: console

    $ mysql -u root -p
    mysql> CREATE DATABASE murano;
    mysql> GRANT ALL PRIVILEGES ON murano.* TO 'murano'@'localhost' \
        IDENTIFIED BY 'MURANO_DBPASS';
    mysql> exit;
..


Install the API service and Engine
==================================

#.  Create a folder which will hold all Murano components.

    .. code-block:: console

        $ mkdir ~/murano
    ..

#.  Clone the Murano git repository to the management server.

    .. code-block:: console

        $ cd ~/murano
        $ git clone https://github.com/stackforge/murano
    ..

#.  Set up Murano config file

    Murano has common config file for API and Engine servicies.

    First, generate sample configuration file, using tox

    .. code-block:: console

        $ tox -e genconfig
    ..

    And make a copy of it for further modifications

    .. code-block:: console
        $ cd ~/murano/murano/etc/murano
        $ cp murano.conf.sample murano.conf
    ..

#.  Edit ``murano.conf`` with your favorite editor. Below is an example
    which contains basic settings your are likely need to configure.

    .. note::

        The example below uses SQLite database. Edit **[database]** section
        if you want to use other database type.
    ..

    .. code-block:: ini

        [DEFAULT]
        debug = true
        verbose = true
        rabbit_host = %RABBITMQ_SERVER_IP%
        rabbit_userid = %RABBITMQ_USER%
        rabbit_password = %RABBITMQ_PASSWORD%
        rabbit_virtual_host = %RABBITMQ_SERVER_VIRTUAL_HOST%
        notification_driver = messagingv2

        ...

        [database]
        backend = sqlalchemy
        connection = sqlite:///murano.sqlite

        ...

        [keystone]
        auth_url = 'http://%OPENSTACK_HOST_IP%:5000/v2.0'

        ...

        [keystone_authtoken]
        auth_uri = 'http://%OPENSTACK_HOST_IP%:5000/v2.0'
        auth_host = '%OPENSTACK_HOST_IP%'
        auth_port = 5000
        auth_protocol = http
        admin_tenant_name = %OPENSTACK_ADMIN_TENANT%
        admin_user = %OPENSTACK_ADMIN_USER%
        admin_password = %OPENSTACK_ADMIN_PASSWORD%

        ...

        [murano]
        url = http://%YOUR_HOST_IP%:8082

        [rabbitmq]
        host = %RABBITMQ_SERVER_IP%
        login = %RABBITMQ_USER%
        password = %RABBITMQ_PASSWORD%
        virtual_host = %RABBITMQ_SERVER_VIRTUAL_HOST%
    ..

#.  Create a virtual environment and install Murano prerequisites. We will use
    *tox* for that. Virtual environment will be created under *.tox* directory.

    .. code-block:: console

        $ cd ~/murano/murano
        $ tox
    ..

#.  Create database tables for Murano.

    .. code-block:: console

        $ cd ~/murano/murano
        $ tox -e venv -- murano-db-manage \
        > --config-file ./etc/murano/murano.conf upgrade
    ..

#.  Open a new console and launch Murano API. A separate terminal is
    required because the console will be locked by a running process.

    .. code-block:: console

        $ cd ~/murano/murano
        $ tox -e venv -- murano-api \
        > --config-file ./etc/murano/murano.conf
    ..

#.  Import Core Murano Library.

    .. code-block:: console

        $ cd ~/murano/murano
        $ tox -e venv -- murano-manage \
        > --config-file ./etc/murano/murano.conf \
        > import-package ./meta/io.murano
    ..

#. Open a new console and launch Murano Engine. A separate terminal is
    required because the console will be locked by a running process.

    .. code-block:: console

        $ cd ~/murano/murano
        $ tox -e venv -- murano-engine --config-file ./etc/murano/murano.conf
    ..


Install Murano Dashboard
========================

 Murano API & Engine services provide the core of Murano. However, your need a
 control plane to use it. This section decribes how to install and run Murano
 Dashboard.

#.  Clone the repository with Murano Dashboard.

    .. code-block:: console

        $ cd ~/murano
        $ git clone https://github.com/stackforge/murano-dashboard
    ..

#.  Create a virtual environment and install dashboard prerequisites. Use *tox* for that.
    According to tox.ini config, this command also installs horizon (openstack dashboard).
    It's not listed in murano-dashboard dependencies,
    since in production murano supposed to be a horizon plugin and is used above existing horizon.

    .. note::

     | By default horizon is installed from the master branch, according to tox config file.
     | Note, that previous murano versions may be incompatible with horizon master.
     | So, to install desired horizon version, edit *tox.ini* file and provide
       in *deps* parameter of [testenv] section link to the desired package
       from http://tarballs.openstack.org/horizon

    ..
    .. code-block:: console

        $ cd ~/murano/murano-dashboard
        $ tox -e venv -- pip freeze
    ..

#.  Copy configuration local settings configuration file.

    .. code-block:: console

        $ cd ~/murano/murano-dashboard/muranodashboard/local
        $ cp local_settings.py.example local_settings.py
    ..

#.  And edit it according to your Openstack installation.

    .. code-block:: console

        $ vim ./local_settings.py
    ..

    .. code-block:: python

        ...
        ALLOWED_HOSTS = '*'

        # Provide OpenStack Lab credentials
        OPENSTACK_HOST = '%OPENSTACK_HOST_IP%'

        ...

        # Set secret key to prevent it's generation
        SECRET_KEY = 'random_string'

        ...

        DEBUG_PROPAGATE_EXCEPTIONS = DEBUG
    ..

    Also, it's better to change default session backend from  browser cookies to database to avoid
    issues with forms during creating applications:

    .. code-block:: python

        ...
        DATABASES = {
            'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': '/tmp/murano-dashboard.sqlite',
            }
        }

        SESSION_ENGINE = 'django.contrib.sessions.backends.db'
    ..

    If you do not plan to get murano service from keystone application catalog,
    provide where murano-api service is running:

    .. code-block:: python

        ...
        MURANO_API_URL = 'http://localhost:8082'
    ..

#.  Prepare murano

    Murano UI is a plugin for Openstack Dashboard (Horizon). Horizon allows dashboards,
    panels and panel groups to be added without modifying the default settings.
    To get more information, go the the official `horizon documentation <http://docs.openstack.org/developer/horizon/topics/settings.html#pluggable-settings-label>`_


    There is special script that sets up murano-dashboard with horizon in one action.
    It is called *prepare_murano.sh* and located under repository root. This script
    copies actual openstack_dashboard settings file from horizon and puts murano plugin file to the right place.
    Openstack_dashboard location parameter should be provided:

    .. code-block:: console

        $ cd ~/murano/murano-dashboard
        $ ./prepare_murano.sh --openstack-dashboard .tox/venv/lib/python2.7/site-packages/openstack_dashboard

    ..

#.  Perform database synchronization.

    Optional step. Needed in case you set up database as a session backend.

    .. code-block:: console

        $ tox -e venv -- python manage.py syncdb
    ..

#.  Run Django server at 127.0.0.1:8000 or provide different IP and PORT parameters.

    .. code-block:: console

        $ tox -e venv -- python manage.py runserver <IP:PORT>
    ..

    Development server will be restarted automatically on every code change.

#.  Open dashboard using url http://localhost:8000

Import Murano Applications
==========================

Murano provides excellent catalog services, but it also requires applications
which to provide. This section describes how to import Murano Applications from
Murano App Incubator.

1.  Clone Murano App Incubator repository.

    .. code-block:: console

        $ cd ~/murano
        $ git clone https://github.com/stackforge/murano-apps
    ..

2.  Import every package you need from this repository, using the command
    below.

    .. code-block:: console

        $ cd ~/murano/murano
        $ tox -e venv -- murano-manage \
        > --config-file ./etc/murano/murano.conf \
        > import-package ../murano-app-incubator/%APPLICATION_DIRECTORY_NAME%

.. include:: configure_network.rst
