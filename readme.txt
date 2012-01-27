This is a Cython-based wrapper around the Saleae Device SDK for the Saleae
family of logic analyzers (http://www.saleae.com/).

Required to make this work is:

Python      (http://python.org/ - tested with version 2.7)
numpy       (http://numpy.scipy.org/)
Cython      (http://cython.org/ - tested with version 0.15.1)
setuptools  (http://pypi.python.org/pypi/setuptools)

You'll also need the Saleae Device SDK library, which you can get from
http://www.saleae.com/, as well as the driver for whatever Logic device
you have installed.  You'll need to sign up for an account and access
http://community.saleae.com/.

I have only built and tested this on Windows, and only with the Logic16.
Sorry I do not have detailed build instructions yet.  There were a couple
things I had to do to make it build on Windows.  I'll get to that soon.

It seems to work quite well.  I have included the source for a PCM/I2S
analyzer which I have hacked together a GUI for.  It decodes up to 4
channels of 50kHz audio data streaming over PCM, and will write them
to .wav files in realtime.  The GUI also can play the audio over a
sound card in realtime, as well as plot FFTs of the audio data, in realtime.
To be honest I was surprised that this worked.  Cython is awesome.  Spread
the word. ;-)

The intent is that this project could be extended to other, real-time
analyzers in Cython and Python.
