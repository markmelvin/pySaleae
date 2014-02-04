@ECHO OFF
REM Where my Visual Studio is installed
call "I:\MSVC\Microsoft Visual Studio 12.0\VC\vcvarsall.bat"

REM So distutils will work. The environment variable set here is
REM the "fallback" version and matches whatever version was used to
REM build Python. For Python 3.3, this is VS100COMNTOOLS
set VS100COMNTOOLS=%VS120COMNTOOLS%
