..
      Copyright 2014 2014 Mirantis, Inc.

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http//www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

==================================
Murano automated tests description
==================================
This page describes automated tests for a Murano project:

* where tests are located
* how they are run
* how execute tests on a local machine
* how to find the root of problems with FAILed tests

Murano continuous integration service
=====================================
Murano project has separate CI server, which runs tests for all commits and verifies that new code does not break anything.

Murano CI uses OpenStack QA cloud for testing infrastructure.

Murano CI url: https://murano-ci.mirantis.com/jenkins/ Anyone can login to that server, using launchpad credentials.

There you can find each job for each repository: one for the **murano** and another one for **murano-dashboard**.

* "gate-murano-dashboard-ubuntu\*" verifies each commit to murano-dashboard
  repository
* "gate-murano-ubuntu\*" verifies each commit to murano repository

Other jobs allow to build and test Murano documentation and perform another useful work to support Murano CI infrastructure.
All jobs are run on fresh installation of operating system and all components are installed on each run.

Murano automated tests: UI tests
================================

The murano project has a web user interface and all possible user scenarios should be tested.
All UI tests are located at the https://git.openstack.org/cgit/openstack/murano-dashboard/tree/muranodashboard/tests/functional

Automated tests for Murano Web UI are written in Python using special Selenium library. This library is used to automate web browser interaction from Python.
For more information please visit https://selenium-python.readthedocs.org/


Prerequisites:
++++++++++++++

* Install the Python module called nose by performing **easy_install nose**
  or **pip install nose**. This will install the nose libraries, as well as
  the nosetests script, which you can use to automatically discover and run tests.
* Install external Python libraries, which are required for Murano Web UI
  tests: **testtools** and **selenium**.
* Verify that you have one of the following web browsers installed:

  * Mozilla Firefox 46.0

    .. note::

       If you do not have firefox package out of the box,
       install and remove it. Otherwise, you will need to install
       dependant libraries manually. To downgrade Firefox:

       .. code-block:: console

          apt-get remove firefox
          wget https://ftp.mozilla.org/pub/firefox/releases/46.0/linux-x86_64/en-US/firefox-46.0.tar.bz2
          tar -xjf firefox-46.0.tar.bz2
          rm -rf /opt/firefox
          mv firefox /opt/firefox46
          ln -s /opt/firefox46/firefox /usr/bin/firefox

  * Google Chrome

* To run the tests on a remote server, configure the remote X server.  Use VNC Software to see the test results in real-time.

  #. Specify the display environment variable:

     .. code-block:: console

        $DISPLAY=: <value>

  #. Configure remote X server and VNC Software by typing:

     .. code-block:: console

        apt-get install xvfb xfonts-100dpi xfonts-75dpi xfonts-cyrillic xorg dbus-x11
        "Xvfb -fp "/usr/share/fonts/X11/misc/" :$DISPLAY -screen 0 "1280x1024x16" &"
        apt-get install --yes x11vnc
        x11vnc -bg -forever -nopw -display :$DISPLAY -ncache 10
        sudo iptables -I INPUT 1 -p tcp --dport 5900 -j ACCEPT

Download and run tests:
+++++++++++++++++++++++

First of all make sure that all additional components are installed.

* Clone murano-dashboard git repository:

  * git clone git://git.openstack.org/openstack/murano-dashboard*

* To change the default settings:

  #. Specify the Murano Repository URL variable for Horizon local settings in ``murano_dashboard/muranodashboard/local/local_settings.d/_50_murano.py``:
     .. code-block:: console

       MURANO_REPO_URL = 'http://localhost:8099'

  #. Copy ``muranodashboard/tests/functional/config/config.conf.sample`` to``config.conf``.

  #. Set appropriate urls and credentials for your OpenStack lab. Only admin users are appropriate.


::

    [murano]

    horizon_url = http://localhost/dashboard
    murano_url = http://localhost:8082
    user = ***
    password = ***
    tenant = ***
    keystone_url = http://localhost:5000/v3



All tests are kept in *sanity_check.py* and divided into 10 test suites:

  * TestSuiteSmoke - verification of Murano panels; check, that could be open without errors.
  * TestSuiteEnvironment - verification of all operations with environment are finished successfully.
  * TestSuiteImage - verification of operations with images.
  * TestSuiteFields - verification of custom fields validators.
  * TestSuitePackages - verification of operations with Murano packages.
  * TestSuiteApplications - verification of Application Catalog page and of application creation process.

  * TestSuiteAppsPagination - verification of apps pagination in case of many applications installed.
  * TestSuiteRepository - verification of importing packages and bundles.
  * TestSuitePackageCategory - verification of main operations with categories.
  * TestSuiteCategoriesPagination - verification of categories pagination in case of many categories created.
  * TestSuiteMultipleEnvironments - verification of ability to apply action to multiple environments.

To specify which tests/suite to run, pass test/suite names on the command line:

  * to run all tests: ``nosetests sanity_check.py``
  * to run a single suite: ``nosetests sanity_check.py:<test suite name>``
  * to run a single test: ``nosetests sanity_check.py:<test suite name>.<test name>``


In case of SUCCESS execution, you should see something like this:

::

    .........................

    Ran 34 tests in 1.440s

    OK

In case of FAILURE, folder with screenshots of the last operation of tests that finished with errors would be created.
It's located in *muranodashboard/tests/functional* folder.

There are also a number of command line options that can be used to control the test execution and generated outputs. For more details about *nosetests*, try:
::

 nosetests -h


Murano Automated Tests: Tempest Tests
=====================================

All Murano services have tempest-based automated tests, which allow to verify API interfaces and deployment scenarios.

Tempest tests for Murano are located at the: https://git.openstack.org/cgit/openstack/murano/tree/murano/tests/functional

The following Python files contains basic tests suites for different Murano components.

API Tests
+++++++++

Murano API tests are run on devstack gate and located at https://git.openstack.org/cgit/openstack/murano/tree/murano/tests/functional/api

* *test_murano_envs.py* contains test suite with actions on murano's environments(create, delete, get and etc.)
* *test_murano_sessions.py* contains test suite with actions on murano's sessions(create, delete, get and etc.)
* *test_murano_services.py* contains test suite with actions on murano's services(create, delete, get and etc.)
* *test_murano_repository.py* contains test suite with actions on murano's package repository

Engine Tests
+++++++++++++++++++

Murano Engine Tests are run on murano-ci : https://git.openstack.org/cgit/openstack/murano/tree/murano/tests/functional/engine

* *base.py* contains base test class and tests with actions on deploy Murano services such as 'Telnet' and 'Apache'.

Command Line Tests
+++++++++++++++++++++++++

Murano CLI tests case are currently in the middle of creation. The current scope is read only operations on a cloud that are hard to test via unit tests.


All tests have description and execution steps in there docstrings.
