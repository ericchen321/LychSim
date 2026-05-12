// Weichao Qiu @ 2017
#pragma once

#include "BaseCameraSensor.h"
#include "LitCamSensor.generated.h"

/**
 * RGB color sensor
 * The alias issue was reported here
 * https://forums.unrealengine.com/development-discussion/rendering/59403-scenecapturecomponent2d-antialiasing
 */
UCLASS(meta = (BlueprintSpawnableComponent))
class LYCHSIM_API ULitCamSensor : public UBaseCameraSensor
{
	GENERATED_BODY()

public:
	ULitCamSensor(const FObjectInitializer& ObjectInitializer);

	virtual void InitTextureTarget(int FilmWidth, int FilmHeight) override;
	virtual void InitTextureTargetB8G8R8A8(int FilmWidth, int FilmHeight);

	bool EnsureTextureTarget();

	void CaptureLit(TArray<FColor>& Image, int& Width, int& Height, int& WarmupFrames, bool bExperimental = false);
};
