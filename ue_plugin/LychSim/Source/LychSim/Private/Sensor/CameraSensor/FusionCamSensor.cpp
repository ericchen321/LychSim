// Weichao Qiu @ 2018
#include "FusionCamSensor.h"
#include "Runtime/Engine/Classes/Camera/CameraComponent.h"
#include "ImageUtil.h"
#include "Serialization.h"
#include "UnrealcvLog.h"
#include "UnrealcvServer.h"

// Sensors included in FusionSensor
#include "LitCamSensor.h"
#include "DepthCamSensor.h"
#include "NormalCamSensor.h"
#include "AnnotationCamSensor.h"

UFusionCamSensor::UFusionCamSensor(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	FString ComponentName;
	ComponentName = FString::Printf(TEXT("%s_%s"), *this->GetName(), TEXT("PreviewCamera"));
	PreviewCamera = CreateDefaultSubobject<UCameraComponent>(*ComponentName);
	PreviewCamera->SetupAttachment(this);

	ComponentName = FString::Printf(TEXT("%s_%s"), *this->GetName(), TEXT("DepthCamSensor"));
	DepthCamSensor = CreateDefaultSubobject<UDepthCamSensor>(*ComponentName);
	FusionSensors.Add(DepthCamSensor);

	ComponentName = FString::Printf(TEXT("%s_%s"), *this->GetName(), TEXT("NormalCamSensor"));
	NormalCamSensor = CreateDefaultSubobject<UNormalCamSensor>(*ComponentName);
	FusionSensors.Add(NormalCamSensor);

	ComponentName = FString::Printf(TEXT("%s_%s"), *this->GetName(), TEXT("AnnotationCamSensor"));
	AnnotationCamSensor = CreateDefaultSubobject<UAnnotationCamSensor>(*ComponentName);
	FusionSensors.Add(AnnotationCamSensor);

	ComponentName = FString::Printf(TEXT("%s_%s"), *this->GetName(), TEXT("LitCamSensor"));
	LitCamSensor = CreateDefaultSubobject<ULitCamSensor>(*ComponentName);
	FusionSensors.Add(LitCamSensor);

	// The config loading code should not be placed into the ctor, otherwise it will break the copy behavior
	FServerConfig& Config = FUnrealcvServer::Get().Config;
	FilmWidth = Config.Width == 0 ? 640 : Config.Width;
	FilmHeight = Config.Height == 0 ? 480 : Config.Height;
	FOV = Config.FOV == 0 ? 90 : Config.FOV;
	// Note: If FOV == 0, the render will give FMod assert error.
	// Need to call update functions after copy operator (in BeginPlay), here just sets value

	for (UBaseCameraSensor* Sensor : FusionSensors)
	{
		if (IsValid(Sensor))
		{
			Sensor->SetupAttachment(this);
		}
		else
		{
			UE_LOG(LogUnrealCV, Warning, TEXT("Invalid sensor is found in the ctor of FusionCamSensor"));
		}
	}
	// SetFilmSize(FilmWidth, FilmHeight); // This should not not be done in CTOR.
}

void UFusionCamSensor::BeginPlay()
{
	Super::BeginPlay();

	SetFilmSize(FilmWidth, FilmHeight);
	SetSensorFOV(FOV);
}

void UFusionCamSensor::OnRegister()
{
	Super::OnRegister();

	// Ensure capture targets exist even when BeginPlay never fires (e.g. editor viewport usage).
	if (FilmWidth <= 0 || FilmHeight <= 0)
	{
		FServerConfig& Config = FUnrealcvServer::Get().Config;
		FilmWidth = Config.Width == 0 ? 640 : Config.Width;
		FilmHeight = Config.Height == 0 ? 480 : Config.Height;
	}

	if (FOV <= 0.f)
	{
		FServerConfig& Config = FUnrealcvServer::Get().Config;
		FOV = Config.FOV == 0 ? 90.f : Config.FOV;
	}

	SetFilmSize(FilmWidth, FilmHeight);
	SetSensorFOV(FOV);

	for (UBaseCameraSensor* Sensor : FusionSensors)
	{
		if (IsValid(Sensor) && !Sensor->IsRegistered())
		{
			Sensor->RegisterComponent();
		}
	}
}

bool UFusionCamSensor::GetEditorPreviewInfo(float DeltaTime, FMinimalViewInfo& ViewOut)
{
	// From CameraComponent
	if (this->IsActive())
	{
		this->LitCamSensor->GetCameraView(DeltaTime, ViewOut);
		return true;
	}
	else
	{
		return false;
	}
}

void UFusionCamSensor::GetLit(TArray<FColor>& LitData, int& Width, int& Height, int& WarmupFrames, ELitMode LitMode, bool bExperimental)
{
	this->LitCamSensor->CaptureLit(LitData, Width, Height, WarmupFrames, bExperimental);
}

void UFusionCamSensor::GetDepth(TArray<float>& DepthData, int& Width, int& Height, EDepthMode DepthMode)
{
	this->DepthCamSensor->CaptureDepth(DepthData, Width, Height);
}

void UFusionCamSensor::GetZBuffer(TArray<float>& ZBufferData, const TArray<AActor*>& Actors, int& Width, int& Height, EDepthMode DepthMode)
{
	this->DepthCamSensor->CaptureZBuffer(ZBufferData, Actors, Width, Height);
}

void UFusionCamSensor::GetNormal(TArray<FColor>& NormalData, int& Width, int& Height)
{
	this->NormalCamSensor->Capture(NormalData, Width, Height);
}

void UFusionCamSensor::GetSeg(TArray<FColor>& ObjMaskData, int& Width, int& Height, ESegMode SegMode)
{
	this->AnnotationCamSensor->CaptureSeg(ObjMaskData, Width, Height);
}

FVector UFusionCamSensor::GetSensorLocation()
{
	return this->GetComponentLocation(); // World space
}

FRotator UFusionCamSensor::GetSensorRotation()
{
	return this->GetComponentRotation(); // World space
}

void UFusionCamSensor::SetSensorLocation(FVector Location)
{
	this->SetWorldLocation(Location);
}

void UFusionCamSensor::SetSensorRotation(FRotator Rotator)
{
	this->SetWorldRotation(Rotator);
}

void UFusionCamSensor::SetFilmSize(int Width, int Height)
{
	this->FilmWidth = Width;
	this->FilmHeight = Height;
	if (Height == 0 || Width == 0)
	{
		UE_LOG(LogTemp, Warning, TEXT("Invalid film size %d x %d"), Width, Height);
		return;
	}
	for (int i = 0; i < FusionSensors.Num(); i++)
	{
		UBaseCameraSensor* Sensor = FusionSensors[i];
		if (IsValid(Sensor))
		{
			Sensor->SetFilmSize(FilmWidth, FilmHeight);
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("Sensor %d within FusionCamSensor is invalid."), i);
		}
	}
}

float UFusionCamSensor::GetSensorFOV()
{
	return this->LitCamSensor->GetFOV();
}

void UFusionCamSensor::SetSensorFOV(float fov)
{
	this->FOV = fov;
	for (UBaseCameraSensor* Sensor: FusionSensors)
	{
		if (IsValid(Sensor))
		{
			Sensor->SetFOV(fov);
		}
	}
}

TArray<UFusionCamSensor*> UFusionCamSensor::GetComponents(AActor* Actor)
{
	TArray<UFusionCamSensor*> Components;
	if (!IsValid(Actor))
	{
		UE_LOG(LogTemp, Warning, TEXT("Actor is invalid"));
		return Components;
	}

	TArray<UActorComponent*> ChildComponents = Actor->K2_GetComponentsByClass(UFusionCamSensor::StaticClass());
	for (UActorComponent* Component : ChildComponents)
	{
		Components.Add(Cast<UFusionCamSensor>(Component));
	}
	return Components;
}

#if WITH_EDITOR
void UFusionCamSensor::PostEditChangeProperty(FPropertyChangedEvent &PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);

	FName PropertyName = (PropertyChangedEvent.Property != NULL) ? PropertyChangedEvent.Property->GetFName() : NAME_None;
	if (PropertyName == GET_MEMBER_NAME_CHECKED(UFusionCamSensor, PresetFilmSize))
	{
		switch(PresetFilmSize)
		{
		case EPresetFilmSize::F640x480:
			SetFilmSize(640, 480);
			break;
		case EPresetFilmSize::F1080p:
			SetFilmSize(1920, 1080);
			break;
		case EPresetFilmSize::F720p:
			SetFilmSize(1280, 720);
			break;
		}
	}
}
#endif


void UFusionCamSensor::SetProjectionType(ECameraProjectionMode::Type ProjectionType)
{
	for (int i = 0; i < FusionSensors.Num(); i++)
	{
		UBaseCameraSensor* Sensor = FusionSensors[i];
		if (IsValid(Sensor))
		{
			Sensor->ProjectionType = ProjectionType;
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("Sensor %d within FusionCamSensor is invalid."), i);
		}
	}
}

void UFusionCamSensor::SetOrthoWidth(float OrthoWidth)
{
	for (int i = 0; i < FusionSensors.Num(); i++)
	{
		UBaseCameraSensor* Sensor = FusionSensors[i];
		if (!IsValid(Sensor))
		{
			UE_LOG(LogTemp, Warning, TEXT("Sensor %d within FusionCamSensor is invalid."), i);
			continue;
		}
		Sensor->OrthoWidth = OrthoWidth;
	}
}

void UFusionCamSensor::SetLitCaptureSource(ESceneCaptureSource CaptureSource)
{
    this->LitCamSensor->CaptureSource = CaptureSource;
}

// Configure the post process settings
void UFusionCamSensor::SetReflectionMethod(EReflectionMethod::Type Method)
{
    // None, Lumen, ScreenSpace, RayTraced
    this->LitCamSensor->PostProcessSettings.bOverride_ReflectionMethod = true;
    this->LitCamSensor->PostProcessSettings.ReflectionMethod = Method;
}

void UFusionCamSensor::SetGlobalIlluminationMethod(EDynamicGlobalIlluminationMethod::Type Method)
{
    // None, Lumen, ScreenSpace, RayTraced, Plugin,
    this->LitCamSensor->PostProcessSettings.bOverride_DynamicGlobalIlluminationMethod = true;
    this->LitCamSensor->PostProcessSettings.DynamicGlobalIlluminationMethod = Method;
}

void UFusionCamSensor::SetExposureMethod(EAutoExposureMethod Method)
{
    this->LitCamSensor->PostProcessSettings.bOverride_AutoExposureMethod = true;
    this->LitCamSensor->PostProcessSettings.AutoExposureMethod = Method;
}

void UFusionCamSensor::SetExposureBias(float ExposureBias)
{
    this->LitCamSensor->PostProcessSettings.bOverride_AutoExposureBias = true;
    this->LitCamSensor->PostProcessSettings.AutoExposureBias = ExposureBias;
}

void UFusionCamSensor::SetAutoExposureSpeed(float SpeedDown, float SpeedUp)
{
    this->LitCamSensor->PostProcessSettings.bOverride_AutoExposureSpeedDown = true;
    this->LitCamSensor->PostProcessSettings.AutoExposureSpeedDown = SpeedDown;
    this->LitCamSensor->PostProcessSettings.bOverride_AutoExposureSpeedUp = true;
    this->LitCamSensor->PostProcessSettings.AutoExposureSpeedUp = SpeedUp;
}

void UFusionCamSensor::SetAutoExposureBrightness(float MinBrightness, float MaxBrightness)
{
    // Brightness range for the auto exposure algorithm
    if (MinBrightness > MaxBrightness)
    {
        UE_LOG(LogUnrealCV, Warning, TEXT("MinBrightness should be smaller than MaxBrightness"));
        return;
    }
    // Auto-Exposure minimum adaptation.
    this->LitCamSensor->PostProcessSettings.bOverride_AutoExposureMinBrightness = true;
    this->LitCamSensor->PostProcessSettings.AutoExposureMinBrightness = MinBrightness;
    // Auto-Exposure
    this->LitCamSensor->PostProcessSettings.bOverride_AutoExposureMaxBrightness = true;
    this->LitCamSensor->PostProcessSettings.AutoExposureMaxBrightness = MaxBrightness;
}

void UFusionCamSensor::SetApplyPhysicalCameraExposure(int ApplyPhysicalCameraExposure)
{
    this->LitCamSensor->PostProcessSettings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
    this->LitCamSensor->PostProcessSettings.AutoExposureApplyPhysicalCameraExposure = ApplyPhysicalCameraExposure;
}


void UFusionCamSensor::SetMotionBlurParams(float MotionBlurAmount, float MotionBlurMax, float MotionBlurPerObjectSize, int MotionBlurTargetFPS)
{
    // Strength of motion blur, 0:off
    this->LitCamSensor->PostProcessSettings.bOverride_MotionBlurAmount = true;
    this->LitCamSensor->PostProcessSettings.MotionBlurAmount = MotionBlurAmount;
    // Max distortion caused by motion blur, in percent of the screen width, 0:off
    this->LitCamSensor->PostProcessSettings.bOverride_MotionBlurMax = true;
    this->LitCamSensor->PostProcessSettings.MotionBlurMax = MotionBlurMax;
    // The minimum projected screen radius for a primitive to be drawn in the velocity pass, percentage of screen width.
    this->LitCamSensor->PostProcessSettings.bOverride_MotionBlurPerObjectSize = true;
    this->LitCamSensor->PostProcessSettings.MotionBlurPerObjectSize = MotionBlurPerObjectSize;
    // Target frame rate for motion blur
    this->LitCamSensor->PostProcessSettings.bOverride_MotionBlurTargetFPS = true;
    this->LitCamSensor->PostProcessSettings.MotionBlurTargetFPS = MotionBlurTargetFPS;
}

void UFusionCamSensor::SetFocalParams(float FocalDistance, float FocalRegion)
{
    this->LitCamSensor->PostProcessSettings.bOverride_DepthOfFieldFocalDistance = true;
    this->LitCamSensor->PostProcessSettings.DepthOfFieldFocalDistance = FocalDistance;
    this->LitCamSensor->PostProcessSettings.bOverride_DepthOfFieldFocalRegion = true;
    this->LitCamSensor->PostProcessSettings.DepthOfFieldFocalRegion = FocalRegion;
}

void UFusionCamSensor::GetIntrinsics(float& Fx, float& Fy, float& Cx, float& Cy, float& FovX, float& FovY)
{
	int32 Width = FilmWidth > 0 ? FilmWidth : 0;
	int32 Height = FilmHeight > 0 ? FilmHeight : 0;

	if (Width <= 0 || Height <= 0)
	{
		if (IsValid(LitCamSensor))
		{
			Width = LitCamSensor->GetFilmWidth();
			Height = LitCamSensor->GetFilmHeight();
		}
	}

	Width = Width <= 0 ? 1 : Width;
	Height = Height <= 0 ? 1 : Height;

	const float FovXDeg = GetSensorFOV();
	const float FovXRad = FMath::DegreesToRadians(FovXDeg);
	FovX = FovXDeg;

	Fx = 0.5f * static_cast<float>(Width) / FMath::Tan(0.5f * FovXRad);
	const float FovYRad = 2.f * FMath::Atan(FMath::Tan(0.5f * FovXRad) * static_cast<float>(Height) / static_cast<float>(Width));
	Fy = 0.5f * static_cast<float>(Height) / FMath::Tan(0.5f * FovYRad);
	FovY = FMath::RadiansToDegrees(FovYRad);

	Cx = (static_cast<float>(Width) - 1.f) * 0.5f;
	Cy = (static_cast<float>(Height) - 1.f) * 0.5f;
}

void UFusionCamSensor::GetPointMaps(
	TArray<FVector>& CameraSpacePoints,
	TArray<FVector>& WorldSpacePoints,
	TArray<FVector>& OpenCVSpacePoints,
	int& Width,
	int& Height,
	bool bIncludeCameraSpace,
	bool bIncludeWorldSpace,
	bool bIncludeOpenCVSpace)
{
	TArray<float> DepthData;
	GetDepth(DepthData, Width, Height);

	if (DepthData.Num() == 0 || Width <= 0 || Height <= 0)
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Failed to capture depth when building point maps."));
		return;
	}

	float Fx = 0.f, Fy = 0.f, Cx = 0.f, Cy = 0.f, FovX = 0.f, FovY = 0.f;
	GetIntrinsics(Fx, Fy, Cx, Cy, FovX, FovY);
	const FTransform SensorTransform = GetComponentTransform();

	const int32 NumPoints = DepthData.Num();
	if (bIncludeCameraSpace)
	{
		CameraSpacePoints.SetNumZeroed(NumPoints);
	}
	else
	{
		CameraSpacePoints.Reset();
	}

	if (bIncludeWorldSpace)
	{
		WorldSpacePoints.SetNumZeroed(NumPoints);
	}
	else
	{
		WorldSpacePoints.Reset();
	}

	if (bIncludeOpenCVSpace)
	{
		OpenCVSpacePoints.SetNumZeroed(NumPoints);
	}
	else
	{
		OpenCVSpacePoints.Reset();
	}

	for (int32 Index = 0; Index < NumPoints; ++Index)
	{
		const float Depth = DepthData[Index];
		if (!FMath::IsFinite(Depth) || Depth <= 0.f)
		{
			continue;
		}

		const int32 U = Index % Width;
		const int32 V = Index / Width;

		const float X_CV = (static_cast<float>(U) - Cx) * Depth / Fx; // right
		const float Y_CV = (static_cast<float>(V) - Cy) * Depth / Fy; // down
		const float Z_CV = Depth; // forward

		// UE camera space: X forward, Y right, Z up (left-handed)
		const FVector CamPoint(Z_CV, X_CV, -Y_CV);

		if (bIncludeCameraSpace)
		{
			CameraSpacePoints[Index] = CamPoint;
		}
		if (bIncludeWorldSpace)
		{
			WorldSpacePoints[Index] = SensorTransform.TransformPosition(CamPoint);
		}
		if (bIncludeOpenCVSpace)
		{
			OpenCVSpacePoints[Index] = FVector(X_CV, Y_CV, Z_CV);
		}
	}
}
