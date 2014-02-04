@echo OFF
REM Build script for the Saleae Cython wrapper

IF "%1"=="clean" (
    rmdir /S /Q build
    del /Q *.pyd
    del /Q *.cpp
) ELSE (
    @echo Hint: You may need to run set_env.bat once to set up the environment for Visual Studio
    python setup.py build_ext --inplace
)
