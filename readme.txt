Introduction
------------

This is a Cython-based wrapper around the Saleae Device SDK for the Saleae
family of logic analyzers (http://www.saleae.com/).

Required to make this work is:

Python      http://python.org/
                 Tested with version 3.3.3

numpy       http://numpy.scipy.org/
                 Used the MKL version for Python 3.3 found here:
                 http://www.lfd.uci.edu/~gohlke/pythonlibs/

Cython      http://cython.org/
                 Used/tested with version 0.20

setuptools  http://pypi.python.org/pypi/setuptools

You'll also need the Saleae Device SDK library, which you can get from
http://www.saleae.com/, as well as the driver for whatever Logic device
you have installed.  To get the Device SDK you'll need to sign up for
an account and access http://community.saleae.com/.

I have only built and tested this on Windows (Win8, 64-bit), and only
with the Logic16.

Build and Installation Instructions
-----------------------------------

Here are the installation and build instructions:

- Install Python 3.3
- Install Cython 0.20
- Install Numpy (MKL version)
- Install setuptools
- Install Saleae Logic 1.1.18 beta (this is the version I used) to
  get the Logic/Logic16 driver
- Get the Saleae Device SDK (I used version 1.1.14) and copy all three of
  SaleaeDevice.dll, SaleaeDevice.lib and SaleaeDeviceApi.h over from the
  device API into the build folder. They have been checked in for reference.

You'll need Microsoft Visual Studio Express to build the Cython modules. I
tried to make it work with Mingw, but I could not get the Saleae Device SDK
libraries converted to work. In the end, I installed Microsoft Visual Studio
Express Desktop 2013.

Once everything is installed, to build the .pyd files (the Cython-ized Python
extension modules), type:

  set_env
  build

You may need to edit set_env.bat depending on your version of Windows
and Visual Studio.

There is a Python example showing how to use the device manager to listen for
events. Once the extension modules are built, just type:

  python device_manager_example.py

If you plug an unplug a Logic or Logic16, the events should be displayed
in the console.

Analyzers
---------

The whole point of this project was to allow analyzers to be written for
the Saleae Logic/Logic16 devices in Python.  Unfortunately, to do anything with
the data coming in at the raw rate off the analyzer (many megabytes per second)
the analyzer needs to be written in Cython.  Python is just too slow.  But it
is actually pretty impressive what Cython can accomplish.  It allows you to write
most of the code in a "Pythonic" way, while do the heavy number crunching in
C/C++ under the covers.  Unfortunately this means that you need to compile your
analyzer into an extension module (.pyd file), but since you already have made it
this far, the hard work is done.  Also, Cython is a great way for making Python
extension modules (.pyd files) that are fully accessible from your Python modules
essentially for free.

To this end, I have included a very simple analyzer that ...

  Coming soon....

*** NOTE: The PCM/I2S analyzer needs to be ported over to the new codebase 
          and Python 3.3. It will not run at the moment, but could be used
          as a reference.

Also included is a PCM/I2S analyzer which I have hacked together a GUI for.
It decodes up to 4 channels of 50kHz audio data streaming over PCM, and will
write them to .wav files in realtime.  The GUI also can play the audio over a
sound card in realtime, as well as plot FFTs of the audio data, in realtime.
To be honest I was surprised that this worked.  Cython is awesome.  Spread
the word. ;-)

The intent is that this project could be extended to other, real-time
analyzers in Cython and Python.
