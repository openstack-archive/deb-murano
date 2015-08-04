.. _DynamicUISpec:

Dynamic UI definition specification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The main purpose of Dynamic UI is to generate application creation
forms "on-the-fly".  The Murano dashboard does not know anything about
applications that will be presented in the catalog and which web forms are required to create
an application instance.  So all application definitions should contain
an instruction, which tells the dashboard how to create an application and what
validations need to be applied. This document will help you compose
a valid UI definition for your application.

File Structure
--------------

The UI definition should be a valid yaml file and should contain the following sections (for version 2):

* **Version** - points out to which syntax version is used, optional
* **Templates** - optional, auxiliary section, used together with an Application section, optional
* **Application** - object model description which will be used for application deployment, required
* **Forms** - web form definitions, required

Version
-------

The latest version of a supported dynamic UI syntax is 2.
This section is optional, the default version is set to 1.
Murano Juno and Kilo supports version 2. Version 1 is obsolete.

Application and Templates
-------------------------

The Application section describes an *application object model*.
This model will be translated into json, and an application will be
deployed according to that json. The application section should
contain all necessary keys that are required by the murano-engine to
deploy an application. Note that under *?* section system part
of the model goes. So murano understands that instead of simple value
MuranoPL object is used. You can pick parameters you got from a user
(they should be described in the Forms section) and pick the right place
where they should be set. To do this `YAQL
<https://github.com/ativelkov/yaql/blob/master/README.md>`_ is
used. Two yaql functions are used for object model generation:

* **generateHostname** is used for machine hostname generation; it accepts 2 arguments: name pattern (string) and index (integer). If '#' symbol is present in name pattern, it will be replaced with the index provided. If pattern is not given, a random name will be generated.
* **repeat** is used to produce a list of data snippets, given the template snippet (first argument) and number of times it should be reproduced (second argument). Inside that template snippet current step can be referenced as *$index*.

.. note:
   Note, that while evaluating YAQL expressions referenced from
   **Application** section (as well as almost all attributes inside
   **Forms** section, see later) *$* root object is set to the list of
   dictionaries with cleaned validated forms' data. For example, to obtain
   a cleaned value of field *name* of form *appConfiguration* , you should reference it
   as *$.appConfiguration.name*. This context will be called as a
   **standard context** throughout the text.

*Example:*

.. code-block:: yaml

   Templates:
     primaryController:
        ?:
          type: io.murano.windows.activeDirectory.PrimaryController
        host:
          ?:
            type: io.murano.windows.Host
          adminPassword: $.serviceConfiguration.adminPassword
          name: generateHostname($.serviceConfiguration.unitNamingPattern, 1)
          flavor: $.instanceConfiguration.flavor
          image: $.instanceConfiguration.osImage

      secondaryController:
        ?:
          type: io.murano.windows.activeDirectory.SecondaryController
        host:
          ?:
            type: io.murano.windows.Host
          adminPassword: $.serviceConfiguration.adminPassword
          name: generateHostname($.serviceConfiguration.unitNamingPattern, $index + 1)
          flavor: $.instanceConfiguration.flavor
          image: $.instanceConfiguration.osImage

   Application:
     ?:
       type: io.murano.windows.activeDirectory.ActiveDirectory
     name: $.serviceConfiguration.name
     primaryController: $primaryController
     secondaryControllers: repeat($secondaryController, $.serviceConfiguration.dcInstances - 1)


Forms
-----

This section describes markup elements for defining forms, which are currently rendered and validated with Django.
Each form has a name, field definitions (mandatory) and validator definitions (optionally).

Note, that each form is splitted into 2 parts:

* **input area** - left side, where all the controls are located
* **description area** - right side, where descriptions of the controls are located

Each field should contain:

* **name** -  system field name, could be any
* **type** - system field type

Currently supported options for **type** attribute are:

* string - text field (no inherent validations) with one-line text input
* boolean - boolean field, rendered as a checkbox
* text - same as string, but with a multi-line input
* integer - integer field with an appropriate validation, one-line text input
* password - text field with validation for strong password, rendered as two masked text inputs (second one is for password confirmation)
* clusterip - specific text field, used for entering cluster IP address (validations for valid IP address syntax and for that IP to belong to a fixed subnet)
* floatingip - specific boolean field, used for specifying whether or not an instance should have floating IP; *DEPRECATED FIELD* - use boolean field instead
* domain - specific field, used for selecting Active Directory domain from a list (or creating a new Active Directory application); *DEPRECATED FIELD* - use io.murano.windows.ActiveDirectory instead
* databaselist - Specific field, a list of databases (comma-separated list of databases' names, where each name has the following syntax first symbol should be latin letter or underscore; subsequent symbols can be latin letter, numeric, underscore, at the sign, number sign or dollar sign), rendered as one-line text input
* image - specific field, used for filtering suitable images by image type provided in murano metadata in glance properties.
* flavor - specific field, used for selection instance flavor from a list
* keypair - specific field, used for selecting a keypair from a list
* azone - specific field, used for selecting instance availability zone from a list
* any other value is considered to be a fully qualified name for some Application package and is rendered as a pair of controls: one for selecting already existing Applications of that type in an Environment, second - for creating a new Application of that type and selecting it

Other arguments (and whether they are required or not) depends on a
field's type and other attributes values. The most common
attributes are the following:

* **label** - name, that will be displayed in the form; defaults to **name** being capitalized.
* **description** - description, that will be displayed in the description area.
  Use yaml line folding character >- to keep the correct formatting during data transferring.
* **descriptionTitle** - title of the description, defaults to **label**; displayed in the description area
* **hidden** whether field should be visible or not in the input area.
  Note that hidden field's description will still be visible in the descriptions area (if given).
  Hidden fields are used storing some data to be used by other, visible fields.
* **minLength**, **maxLength** (for string fields) and **minValue**, **maxValue** (for integer fields) are transparently translated into django validation properties.
* **validators** is a list of dictionaries, each dictionary should at least have *expr* key, under that key either some `YAQL <https://github.com/stackforge/yaql/blob/master/README.rst>`_ expression is stored, either one-element dictionary with *regexpValidator* key (and some regexp string as value). Another possible key of a validator dictionary is *message*, and although it is not required, it is highly desirable to specify it - otherwise, when validator fails (i.e. regexp doesn't match or YAQL expression evaluates to false) no message will be shown. Note that field-level validators use YAQL context different from all other attributes and section: here *$* root object is set to the value of field being validated (to make expressions shorter).
* **widgetMedia** sets some custom *CSS* and *JavaScript* used for the field's widget rendering. Note, that files should be placed to Django static folder in advance.
  Mostly they are used to do some client-side field enabling/disabling, hiding/unhiding etc.
  This is a temporary field which will be dropped once Version 3 of Dynamic UI is implemented (since it will transparently translate YAQL expressions into the appropriate *JavaScript*).
* **requirements** is used only with flavor field and prevents user to pick unstable for a deployment flavor.
  It allows to set minimum ram (in MBs), disk space (in GBs) or virtual CPU quantity.

  Example that shows how to hide items smaller than regular 'small' flavor in a flavor select field:

  .. code-block:: yaml

   - name: flavor
          type: flavor
          label: Instance flavor
          requirements:
              min_disk: 20
              min_vcpus: 2
              min_memory_mb: 2048

Besides field-level validators, form-level validators also exist. They
use **standard context** for YAQL evaluation and are required when
there is a need to validate some form's constraint across several
fields.

*Example*

.. code-block:: yaml

 Forms:
   - serviceConfiguration:
       fields:
         - name: name
           type: string
           label: Service Name
           description: >-
             To identify your service in logs please specify a service name
         - name: dcInstances
           type: integer
           hidden: true
           initial: 1
           required: false
           maxLength: 15
           helpText: Optional field for a machine hostname template
         - name: unitNamingPattern
           type: string
           label: Instance Naming Pattern
           required: false
           maxLength: 64
           regexpValidator: '^[a-zA-Z][-_\w]*$'
           errorMessages:
            invalid: Just letters, numbers, underscores and hyphens are allowed.
          helpText: Just letters, numbers, underscores and hyphens are allowed.
          description: >-
            Specify a string that will be used in a hostname instance.
            Just A-Z, a-z, 0-9, dash, and underline are allowed.


   - instanceConfiguration:
         fields:
           - name: title
             type: string
             required: false
             hidden: true
             descriptionTitle: Instance Configuration
             description: Specify some instance parameters based on which service will be created.
           - name: flavor
             type: flavor
             label: Instance flavor
             description: >-
               Select a flavor registered in Openstack. Consider that service performance
               depends on this parameter.
             required: false
           - name: osImage
             type: image
             imageType: windows
             label: Instance image
             description: >-
               Select valid image for a service. Image should already be prepared and
               registered in glance.
           - name: availabilityZone
             type: azone
             label: Availability zone
             description: Select an availability zone, where service will be installed.
             required: false

