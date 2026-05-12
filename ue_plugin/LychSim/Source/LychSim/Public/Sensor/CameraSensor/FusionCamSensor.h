// Weichao Qiu @ 2017
#pragma once

#include "Runtime/Engine/Classes/Components/PrimitiveComponent.h"
#include "Runtime/Engine/Classes/Camera/CameraTypes.h"
#include "FusionCamSensor.generated.h"

UENUM(BlueprintType)
enum class ELitMode : uint8
{
	Lit,
	Slow
};

UENUM(BlueprintType)
enum class EDepthMode : uint8
{
	PlaneDepth,
	DistToCamCenter
};

UENUM(BlueprintType)
enum class ESegMode : uint8
{
	AnnotationComponent,
	VertexColor,
	CustomStencil
};

UENUM(BlueprintType)
enum class EPresetFilmSize : uint8
{
	F640x480,
	F720p,
	F1080p
};

UCLASS(meta = (BlueprintSpawnableComponent))
class LYCHSIM_API UFusionCamSensor : public UPrimitiveComponent
{
	GENERATED_BODY()

public:
	UFusionCamSensor(const FObjectInitializer& ObjectInitializer);

	virtual void OnRegister() override;
	virtual bool GetEditorPreviewInfo(float DeltaTime, FMinimalViewInfo& ViewOut);

	/** Get rgb data */
	UFUNCTION(BlueprintPure, Category = "lychsim")
	void GetLit(TArray<FColor>& LitData, int& InOutWidth, int& InOutHeight, int& WarmupFrames, ELitMode LitMode = ELitMode::Lit, bool bExperimental = false);

	/** Get depth data */
	UFUNCTION(BlueprintPure, Category = "lychsim")
	void GetDepth(TArray<float>& DepthData, int& InOutWidth, int& InOutHeight, EDepthMode DepthMode = EDepthMode::PlaneDepth);

	UFUNCTION(BlueprintPure, Category = "lychsim")
	void GetZBuffer(TArray<float>& ZBufferData, const TArray<AActor*>& Actors, int& Width, int& Height, EDepthMode DepthMode = EDepthMode::PlaneDepth);

	/** Get surface normal data */
	UFUNCTION(BlueprintPure, Category = "lychsim")
	void GetNormal(TArray<FColor>& NormalData, int& Width, int& Height);

	/** Get object mask data, the annotation color can be extracted from FObjectAnnotator */
	UFUNCTION(BlueprintPure, Category = "lychsim")
	void GetSeg(TArray<FColor>& ObjMaskData, int& Width, int& Height, ESegMode SegMode = ESegMode::AnnotationComponent);

	UFUNCTION(BlueprintPure, Category = "lychsim")
	FVector GetSensorLocation();

	UFUNCTION(BlueprintPure, Category = "lychsim")
	FRotator GetSensorRotation();

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetSensorLocation(FVector Location);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetSensorRotation(FRotator Rotator);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetFilmSize(int Width, int Height);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	float GetFilmWidth() { return FilmWidth; }

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	float GetFilmHeight() { return FilmHeight; }

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	float GetSensorFOV();

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetSensorFOV(float FOV);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetProjectionType(ECameraProjectionMode::Type ProjectionType);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetOrthoWidth(float OrthoWidth);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetLitCaptureSource(ESceneCaptureSource CaptureSource);

    UFUNCTION(BlueprintCallable, Category = "lychsim")
    void SetReflectionMethod(EReflectionMethod::Type Method);

    UFUNCTION(BlueprintCallable, Category = "lychsim")
    void SetGlobalIlluminationMethod(EDynamicGlobalIlluminationMethod::Type Method);

    UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetExposureMethod(EAutoExposureMethod ExposureMethod);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetExposureBias(float ExposureBias);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetAutoExposureSpeed(float ExposureSpeedDown, float ExposureSpeedUp);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetAutoExposureBrightness(float MinBrightness, float MaxBrightness);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetApplyPhysicalCameraExposure(int ApplyPhysicalCameraExposure);

	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void SetMotionBlurParams(float MotionBlurAmount, float MotionBlurMax, float MotionBlurPerObjectSize, int MotionBlurTargetFPS);

    UFUNCTION(BlueprintCallable, Category = "lychsim")
    void SetFocalParams(float FocalDistance, float FocalRegion);

	/** Compute point map from the current depth buffer. */
	UFUNCTION(BlueprintCallable, Category = "lychsim")
	void GetPointMaps(
		TArray<FVector>& CameraSpacePoints,
		TArray<FVector>& WorldSpacePoints,
		TArray<FVector>& OpenCVSpacePoints,
		int& Width,
		int& Height,
		bool bIncludeCameraSpace = true,
		bool bIncludeWorldSpace = true,
		bool bIncludeOpenCVSpace = true);

	/** Get camera intrinsics derived from film size and FOV. */
	UFUNCTION(BlueprintPure, Category = "lychsim")
	void GetIntrinsics(float& Fx, float& Fy, float& Cx, float& Cy, float& FovX, float& FovY);
	// UFUNCTION(BlueprintPure, Category = "lychsim")
	// float GetFilmHeight();

	// UFUNCTION(BlueprintPure, Category = "lychsim")
	// float GetFilmWidth();

	// void SetFilmSize(int Width, int Height);

	UPROPERTY(meta = (AllowPrivateAccess= "true"))
	class UCameraComponent* PreviewCamera;

	virtual void BeginPlay() override;


	static TArray<UFusionCamSensor*> GetComponents(AActor* Actor);

#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent &PropertyChangedEvent) override;
#endif

	FORCEINLINE class ULitCamSensor* GetLitCamSensor() const { return LitCamSensor; }

private:
	UPROPERTY(EditInstanceOnly, meta=(AllowPrivateAccess = "true"), Category = "lychsim")
	EPresetFilmSize PresetFilmSize;

	UPROPERTY(EditInstanceOnly, meta=(AllowPrivateAccess = "true"), Category = "lychsim")
	int FilmWidth;

	UPROPERTY(EditInstanceOnly, meta=(AllowPrivateAccess = "true"), Category = "lychsim")
	int FilmHeight;

	UPROPERTY(EditInstanceOnly, meta=(AllowPrivateAccess = "true"), Category = "lychsim")
	float FOV;

protected:
	UPROPERTY()
	TArray<class UBaseCameraSensor*> FusionSensors;

	UPROPERTY(EditDefaultsOnly, Category = "lychsim")
	class UDepthCamSensor* DepthCamSensor;

	UPROPERTY(EditDefaultsOnly, Category = "lychsim")
	class UNormalCamSensor* NormalCamSensor;

	UPROPERTY(EditDefaultsOnly, Category = "lychsim")
	class UAnnotationCamSensor* AnnotationCamSensor;

	UPROPERTY(EditDefaultsOnly, Category = "lychsim")
	class ULitCamSensor* LitCamSensor;

	/** This preview camera is used for UE version < 4.17 which only support UCameraComponent PIP preview
	See the difference between
	https://github.com/EpicGames/UnrealEngine/blob/4.17/Engine/Source/Editor/LevelEditor/Private/SLevelViewport.cpp#L3927
	and
	https://github.com/EpicGames/UnrealEngine/blob/4.16/Engine/Source/Editor/LevelEditor/Private/SLevelViewport.cpp#L3908
	*/


};
