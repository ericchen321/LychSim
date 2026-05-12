#include "Utils/DataUtil.h"

#include "ImageUtil.h"
#include "Serialization.h"

using namespace LychSim;

EFilenameType LychSim::ParseFilenameType(const FString& Filename)
{
	bool bIncludeDot = false;
	FString FileExtension = FPaths::GetExtension(Filename);
	FileExtension.ToLowerInline();

	// A hacky way to check whether the input is just a file extension
	int DotIndex;
	if (!Filename.FindChar('.', DotIndex)) FileExtension = Filename;

	if (FileExtension == Filename) // The filename only contains extension, which means the binary mode
	{
		if (FileExtension == TEXT("png")) return EFilenameType::PngBinary;
		if (FileExtension == TEXT("bmp")) return EFilenameType::BmpBinary;
		if (FileExtension == TEXT("npy")) return EFilenameType::NpyBinary;
	}
	else
	{
		if (FileExtension == TEXT("png")) return EFilenameType::Png;
		if (FileExtension == TEXT("bmp")) return EFilenameType::Bmp;
		if (FileExtension == TEXT("npy")) return EFilenameType::Npy;
		if (FileExtension == TEXT("exr")) return EFilenameType::Exr;
	}
	return EFilenameType::Invalid;
}

FExecStatus LychSim::SerializeData(const TArray<FColor>& Data, int Width, int Height, const FString& Filename, bool ChannelFirst)
{
	static FImageUtil ImageUtil;
	EFilenameType FilenameType = ParseFilenameType(Filename);

	const int Channel = 4;

	TArray<uint8> BinaryData;
	switch (FilenameType)
	{
	case EFilenameType::BmpBinary:
		ImageUtil.ConvertToBmp(Data, Width, Height, BinaryData);
		return FExecStatus::Binary(BinaryData);
	case EFilenameType::Bmp:
		ImageUtil.SaveBmpFile(Data, Width, Height, Filename);
		return FExecStatus::OK(Filename);
	case EFilenameType::PngBinary:
		ImageUtil.ConvertToPng(Data, Width, Height, BinaryData);
		return FExecStatus::Binary(BinaryData);
	case EFilenameType::Png:
		ImageUtil.SavePngFile(Data, Width, Height, Filename);
		return FExecStatus::OK(Filename);
	case EFilenameType::NpyBinary:
		if (ChannelFirst)
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Height, Channel, Width);
		}
		else
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Width, Height, Channel);
		}
		return FExecStatus::Binary(BinaryData);
	}
	return FExecStatus::Error(FString::Printf(TEXT("Invalid filename type, filename %s"), *Filename));
}

FExecStatus LychSim::SerializeData4D(const TArray<TArray<FColor>>& Data, int Time, int Width, int Height, const FString& Filename, bool ChannelFirst)
{
	static FImageUtil ImageUtil;
	EFilenameType FilenameType = ParseFilenameType(Filename);

	const int Channel = 4;

	TArray<uint8> BinaryData;
	switch (FilenameType)
	{
	case EFilenameType::NpyBinary:
		if (ChannelFirst)
		{
			BinaryData = FSerializationUtils::Array2Npy4D(Data, Time, Height, Channel, Width);
		}
		else
		{
			BinaryData = FSerializationUtils::Array2Npy4D(Data, Time, Width, Height, Channel);
		}
		return FExecStatus::Binary(BinaryData);
	}
	return FExecStatus::Error(FString::Printf(TEXT("Invalid filename type, filename %s"), *Filename));
}

FExecStatus LychSim::SerializeData(const TArray<FFloat16Color>& Data, int Width, int Height, const FString& Filename, bool ChannelFirst)
{
	static FImageUtil ImageUtil;
	EFilenameType FilenameType = ParseFilenameType(Filename);

	TArray<uint8> BinaryData;
	int Channel = Data.Num() / (Width * Height);
	switch (FilenameType)
	{
	case EFilenameType::NpyBinary:
		if (ChannelFirst)
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Height, Channel, Width);
		}
		else
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Width, Height, Channel);
		}
		return FExecStatus::Binary(BinaryData);
	case EFilenameType::Npy:
		if (ChannelFirst)
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Height, Channel, Width);
		}
		else
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Width, Height, Channel);
		}
		ImageUtil.SaveFile(BinaryData, Filename);
		return FExecStatus::OK(Filename);
	}
	return FExecStatus::Error(FString::Printf(TEXT("Invalid filename type, filename %s"), *Filename));
}

FExecStatus LychSim::SerializeData(const TArray<float>& Data, int Width, int Height, const FString& Filename, bool ChannelFirst)
{
	static FImageUtil ImageUtil;
	EFilenameType FilenameType = ParseFilenameType(Filename);

	TArray<uint8> BinaryData;
	int Channel = Data.Num() / (Width * Height);
	switch (FilenameType)
	{
	case EFilenameType::NpyBinary:
		if (ChannelFirst)
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Height, Channel, Width);
		}
		else
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Width, Height, Channel);
		}
		return FExecStatus::Binary(BinaryData);
	case EFilenameType::Npy:
		if (ChannelFirst)
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Height, Channel, Width);
		}
		else
		{
			BinaryData = FSerializationUtils::Array2Npy(Data, Width, Height, Channel);
		}
		ImageUtil.SaveFile(BinaryData, Filename);
		return FExecStatus::OK(Filename);
	}
	return FExecStatus::Error(FString::Printf(TEXT("Invalid filename type, filename %s"), *Filename));
}
