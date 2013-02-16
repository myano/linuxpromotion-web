linuxpromotion.org sources
--------------------------
    
    This repository contains Linux Promotion website sources. You're free to
    use our site generation tool for your own site, it's free software!

Build requirements
------------------

    * Python 3
    * inkscape
    * optipng

To test
-------

    $ python3 lasg/lasg.py test
    
    Open test/index.html

To release
----------

    $ python3 lasg/lasg.py release
    
    Copy all files from "release" directory into the root of the website.
