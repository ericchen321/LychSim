#pragma once

#include "CoreMinimal.h"
#include "CommandHandler.h"

namespace LychSim
{
    enum class EFilenameType
    {
	    Png,
	    Npy,
	    Exr,
	    Bmp,
	    PngBinary,
	    NpyBinary,
	    BmpBinary,
	    Invalid, // Unrecognized filename type
    };

    LYCHSIM_API EFilenameType ParseFilenameType(const FString& Filename);
    LYCHSIM_API FExecStatus SerializeData(const TArray<FColor>& Data, int Width, int Height, const FString& Filename, bool ChannelFirst = false);
    LYCHSIM_API FExecStatus SerializeData4D(const TArray<TArray<FColor>>& Data, int Time, int Width, int Height, const FString& Filename, bool ChannelFirst = false);
	LYCHSIM_API FExecStatus SerializeData(const TArray<FFloat16Color>& Data, int Width, int Height, const FString& Filename, bool ChannelFirst = false);
	LYCHSIM_API FExecStatus SerializeData(const TArray<float>& Data, int Width, int Height, const FString& Filename, bool ChannelFirst = false);

    template<class T>
	void SaveData(const TArray<T>& Data, int Width, int Height, const TArray<FString>& Args, FExecStatus& Status, bool ChannelFirst = false)
    {
        if (Args.Num() != 2)
    	{
    		FString ArgsStr = FString::Join(Args, TEXT(", "));
    		Status = FExecStatus::Error(FString::Printf(TEXT("Filename can not be empty. Args: %s"), *ArgsStr));
    		return;
    	}
    	FString Filename = Args[1];
	    if (Data.Num() == 0)
	    {
		    Status = FExecStatus::Error("Captured data is empty");
		    return;
	    }
	    Status = SerializeData(Data, Width, Height, Filename, ChannelFirst);
	    return;
    }

	template<class T>
	void SaveData4D(const TArray<T>& Data, int Time, int Width, int Height, const TArray<FString>& Args, FExecStatus& Status, bool ChannelFirst = false)
    {
    	FString Filename = Args.Last();
	    if (Data.Num() == 0)
	    {
		    Status = FExecStatus::Error("Captured data is empty");
		    return;
	    }
	    Status = SerializeData4D(Data, Time, Width, Height, Filename, ChannelFirst);
	    return;
    }

	template<class T>
	void SaveDataNPY(const TArray<T>& Data, int Width, int Height, FExecStatus& Status, bool ChannelFirst = false)
    {
	    FString Filename = TEXT("npy");
	    if (Data.Num() == 0)
	    {
		    Status = FExecStatus::Error("Captured data is empty");
		    return;
	    }
	    Status = SerializeData(Data, Width, Height, Filename, ChannelFirst);
	    return;
    }
}
