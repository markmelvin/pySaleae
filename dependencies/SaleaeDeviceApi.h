#ifndef SALEAE_DEVICE_API_H
#define SALEAE_DEVICE_API_H

#ifndef LOGICTYPES
	#define LOGICTYPES 

	typedef char S8;
	typedef short S16; 
	typedef int S32;
	typedef long long int S64;

	typedef unsigned char U8;
	typedef unsigned short U16;
	typedef unsigned int U32;
	typedef unsigned long long int U64; 
	typedef signed long long int S64;

	#ifndef NULL
		#define NULL 0
	#endif
#endif

#include <vector>

class GenericInterface;
class LogicInterface;
class GenericDevice;
class LogicAnalyzerDevice;
class LogicDevice;
class Logic16Device;
class DevicesManager;  
struct Logic16Data;

#if defined(API_RELEASE)
	#if defined(WIN32)
		#define SALEAE_DEVICE_API __declspec(dllexport)
	#else
		#define SALEAE_DEVICE_API __attribute__ ((visibility("default")))
		#define __stdcall
	#endif
#else
	#define SALEAE_DEVICE_API
	#ifndef WIN32
		#define __stdcall
	#endif
#endif

class SALEAE_DEVICE_API DevicesManagerInterface
{
public:
	static void BeginConnect();  //Call this function to start connecting to Logic.  Wait for a OnConnect callback before talking with Logic.
	static void RegisterOnConnect( void (__stdcall *callback)( U64 device_id, GenericInterface* device_interface, void* user_data ), void* user_data = NULL ); //Callback registration
	static void RegisterOnDisconnect( void (__stdcall *callback)( U64 device_id, void* user_data ), void* user_data = NULL );  //Callback registration
	static void DeleteU8ArrayPtr( U8* array_ptr ); //use this to delete memory provided to you from the SDK. i.e. In Logic's OnReadData callback

private:
	static bool mInitVar;
	static bool InitFunc();
};

//Ignore:
class SALEAE_DEVICE_API GenericInterface
{
public:
	
protected:
	GenericInterface();
	virtual void VirtualFunction();
};


class SALEAE_DEVICE_API LogicAnalyzerInterface : public GenericInterface
{
public:
	//General
	bool IsUsb2pt0();   //See if the device is a USB 2.0 device (480mbps) or Full speed (12mbps).
	bool IsStreaming();  //See if the device is reading/writing. In case you arn't keeping track.
	void SetSampleRateHz( U32 sample_rate_hz );	 //Set the sample rate.  Must be a supported value, i.e.:  24000000, 16000000, 12000000, 8000000, 4000000, 2000000, 1000000, 500000, 250000, 200000, 100000, 50000, 25000
	U32 GetSampleRateHz( );	//Get the current sample rate						
	//std::vector<U32> GetSupportedSampleRates();  //get a vector of all the supported sample rates
	S32 GetSupportedSampleRates( U32* buffer, U32 count ); //reports the supported sample rates of a device. pass in an array of at least
	U32 GetChannelCount();	//get the number if channels -- ignore this.

	void RegisterOnReadData( void (__stdcall *callback)( U64 device_id, U8* data, U32 data_length, void* user_data ), void* user_data = NULL );  //Callback Registration
	void RegisterOnWriteData( void (__stdcall *callback)( U64 device_id, U8* data, U32 data_length, void* user_data ), void* user_data = NULL );  //Callback Registration
	void RegisterOnError( void (__stdcall *callback)( U64 device_id, void* user_data ), void* user_data = NULL ); //Callback Registration

protected:
	virtual void OnReadData( U64 device_id, U8* data, U32 data_length );
	void OnWriteData( U64 device_id, U8* data, U32 data_length );
	void OnError( U64 device_id );

	void (__stdcall *mOnReadData)( U64 device_id, U8* data, U32 data_length, void* user_data );
	void (__stdcall *mOnWriteData)( U64 device_id, U8* data, U32 data_length, void* user_data );
	void (__stdcall *mOnError)( U64 device_id, void* user_data );
	void* mOnReadDataUserData;
	void* mOnWriteDataUserData;
	void* mOnErrorUserData;

	LogicAnalyzerDevice* mLogicAnalyzerDevice;
	LogicAnalyzerInterface( LogicAnalyzerDevice* logic_analyzer_device );
};

class SALEAE_DEVICE_API LogicInterface : public LogicAnalyzerInterface
{
public:
	LogicInterface( LogicDevice* logic_device );

	void ReadStart( ); //Start data collection.  You can get the resulting data in your OnReadData callback.
	void WriteStart( ); //Start writing out data.  Your OnWriteData callback will be called to provide the data to Logic.
	void Stop( ); //Stop data collection.  Only use if data collection is actually in progress.

	//Single Byte Data
	U8 GetInput( );					//Get the current byte Logic is reading.  Don't do this while you're doing the Read or Write streaming above.
	void SetOutput( U8 val );		//Make logic output a particular byte value.  Don't do this while you're doing the Read or Write streaming above.

protected:
	LogicDevice* mLogicDevice;
};

class SALEAE_DEVICE_API Logic16Interface : public LogicAnalyzerInterface
{
public:
	Logic16Interface( Logic16Device* logic_16_device );

	void ReadStart( ); //Start data collection.  You can get the resulting data in your OnReadData callback.
	void Stop( ); //Stop data collection.  Only use if data collection is actually in progress.

	void SetActiveChannels( U32* channels, U32 count ); //Set capture channels. Pass in an array of channel indexes and the number of channels.
	U32 GetActiveChannels( U32* channels );	//Get capture channels. pass in an array of at least 16 elements. Returns the number of channels in the array.

	void SetUse5Volts( bool use_5_volts ); //Set the input to use 5 volt logic thresholds. Use false for all other voltages ( 3.3v, 2.5v, 1.8v )
	bool GetUse5Volts(); //Get the current digital IO threshold.

protected:
	virtual void OnReadData( U64 device_id, U8* data, U32 data_length );
	Logic16Device* mLogic16Device;
	struct Logic16Data* mData;
};

#endif //SALEAE_DEVICE_API_H












