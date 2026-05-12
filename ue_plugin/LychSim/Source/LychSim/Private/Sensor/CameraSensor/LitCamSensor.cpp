// Weichao Qiu @ 2017
#include "LitCamSensor.h"
#include "UnrealcvLog.h"
#include "UnrealcvStats.h"

#include "Runtime/Engine/Classes/Engine/Engine.h"
#include "TextureResource.h"

DECLARE_CYCLE_STAT(TEXT("ULitCamSensor::CaptureLit"), STAT_CaptureLit, STATGROUP_UnrealCV);

ULitCamSensor::ULitCamSensor(const FObjectInitializer& ObjectInitializer) :
	Super(ObjectInitializer)
{
}

// void ULitCamSensor::SetupRenderTarget()
// {
// 	bool bUseLinearGamma = false;
// 	TextureTarget->InitCustomFormat(FilmWidth, FilmHeight, EPixelFormat::PF_B8G8R8A8, bUseLinearGamma);
// }

// bool bUseLinearGamma = false;
// bool bUseLinearGamma = true;  // true by default
// bUseLinearGamma requires CaptureEveryFrame!
// TextureTarget->InitAutoFormat(Width, Height);
// TextureTarget->TargetGamma = GEngine->GetDisplayGamma();
// TextureTarget->TargetGamma = 1;

void ULitCamSensor::InitTextureTarget(int filmWidth, int filmHeight)
{
	TextureTarget = NewObject<UTextureRenderTarget2D>(this);
	TextureTarget->InitAutoFormat(filmWidth, filmHeight);
	TextureTarget->TargetGamma = GEngine->GetDisplayGamma();
}

void ULitCamSensor::InitTextureTargetB8G8R8A8(int filmWidth, int filmHeight)
{
	TextureTarget = NewObject<UTextureRenderTarget2D>(this);
    TextureTarget->SRGB = true;
    TextureTarget->InitCustomFormat(filmWidth, filmHeight, PF_B8G8R8A8, false);
	TextureTarget->TargetGamma = GEngine->GetDisplayGamma();
    TextureTarget->UpdateResourceImmediate(true);
}

bool ULitCamSensor::EnsureTextureTarget()
{
	if (!CheckTextureTarget() || TextureTarget->GetFormat() != PF_B8G8R8A8)
	{
		InitTextureTargetB8G8R8A8(this->FilmWidth, this->FilmHeight);
		if (!CheckTextureTarget())
		{
			UE_LOG(LogUnrealCV, Error, TEXT("Failed to initialize TextureTarget."));
			return false;
		}
	}

	this->bCaptureEveryFrame = false;
	this->bAlwaysPersistRenderingState = true;
	this->bUseRayTracingIfEnabled = true;

	this->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	this->PostProcessSettings.bOverride_DynamicGlobalIlluminationMethod = true;
	this->PostProcessSettings.DynamicGlobalIlluminationMethod = EDynamicGlobalIlluminationMethod::Lumen;
	this->PostProcessSettings.bOverride_ReflectionMethod = true;
	this->PostProcessSettings.ReflectionMethod = EReflectionMethod::Lumen;

	return true;
}

void ULitCamSensor::CaptureLit(TArray<FColor>& Image, int& Width, int& Height, int& WarmupFrames, bool bExperimental)
{
	SCOPE_CYCLE_COUNTER(STAT_CaptureLit);
	if (!CheckTextureTarget())
	{
		InitTextureTarget(this->FilmWidth, this->FilmHeight);
		if (!CheckTextureTarget())
		{
			UE_LOG(LogUnrealCV, Error, TEXT("Failed to initialize TextureTarget."));
			return;
		}
	}
	this->bCaptureEveryFrame = false;
	this->bAlwaysPersistRenderingState = true;
	this->bUseRayTracingIfEnabled = true;

	this->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	this->PostProcessSettings.bOverride_DynamicGlobalIlluminationMethod = true;
	this->PostProcessSettings.DynamicGlobalIlluminationMethod = EDynamicGlobalIlluminationMethod::Lumen;
	this->PostProcessSettings.bOverride_ReflectionMethod = true;
	this->PostProcessSettings.ReflectionMethod = EReflectionMethod::Lumen;

	if (bExperimental)
	{
		this->ShowFlags.SetTemporalAA(false);

		this->PostProcessSettings.bOverride_MotionBlurAmount = true;
		this->PostProcessSettings.MotionBlurAmount = 0.0f;
		this->ShowFlags.SetMotionBlur(false);

		this->PostProcessSettings.bOverride_DepthOfFieldScale = true;
		this->PostProcessSettings.DepthOfFieldScale = 0.0f;
		this->ShowFlags.SetDepthOfField(false);
	}

	for (int32 i = 0; i < WarmupFrames; i++)
	{
		this->CaptureScene();
		FlushRenderingCommands();
	}

	this->CaptureScene();
	FReadSurfaceDataFlags ReadSurfaceDataFlags;
	ReadSurfaceDataFlags.SetLinearToGamma(false);
	// TextureTarget->GetRenderTargetResource()->ReadPixels(Image, ReadSurfaceDataFlags);
	TextureTarget->GameThread_GetRenderTargetResource()->ReadPixels(Image, ReadSurfaceDataFlags);
	if (Image.Num() == 0)
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Captured lit data is empty."));
	}
	Width = GetFilmWidth();
	Height = GetFilmHeight();
}
