#ifndef _THOR_SCSI_CUSTOM_NONLINEAR_KICKER_INTERPOLATION_H_
#define _THOR_SCSI_CUSTOM_NONLINEAR_KICKER_INTERPOLATION_H_ 1

#include <thor_scsi/custom/aircoil_interpolation.h>

namespace thor_scsi::custom {

    struct _position  {
	double x;
	double y;
    };

    typedef struct _position position_t;

    const std::vector<aircoil_filament_t> construct_aircoil_filaments(const std::vector<aircoil_filament_t>& filaments_one_quater);

    template<class C>
    class NonLinearKickerInterpolationKnobbed: public AirCoilMagneticFieldKnobbed<C>  {

    public:
	NonLinearKickerInterpolationKnobbed(const std::vector<aircoil_filament_t> filaments_one_quater)
	    : AirCoilMagneticFieldKnobbed<C>(construct_aircoil_filaments(filaments_one_quater))
	    {}

	inline void setFilaments(const std::vector<aircoil_filament_t> filaments_one_quater) {
        this->setFilaments(construct_aircoil_filaments(filaments_one_quater));
    }
	void show(std::ostream&, int level) const override;
    };

    typedef  NonLinearKickerInterpolationKnobbed<thor_scsi::core::StandardDoubleType> NonLinearKickerInterpolation;
} //namespace thor_scsi::custom

#endif /* _THOR_SCSI_CUSTOM_NONLINEAR_KICKER_INTERPOLATION_H_ */
