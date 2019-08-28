# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# Copyright (c) 2019, Eurecat / UPF
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   @file   simulate_array.py
#   @author Andrés Pérez-López
#   @date   22/08/2019
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

import numpy as np
import scipy.special
import masp.array_response_simulator as asr
import masp.utils
from masp.validate_data_types import _validate_int, _validate_ndarray_2D, _validate_string, _validate_float, \
    _validate_ndarray_1D, _validate_ndarray


def simulate_sph_array(N_filt, mic_dirs_rad, src_dirs_rad, arrayType, R, N_order, fs, dirCoef=None):
    """
    Simulate the impulse responses of a spherical array.

    Parameters
    ----------
    N_filt : int
        Number of frequencies where to compute the response. It must be even.
    mic_dirs_rad: ndarray
        Directions of microphone capsules, in radians.
        Expressed in [azi, ele] pairs. Dimension = (N_mic, C-1).
    src_dirs_rad: ndarray
        Direction of arrival of the indicent plane waves, in radians.
         Expressed in [azi, ele] pairs. Dimension = (N_doa, C-1).
    arrayType: str
        'open', 'rigid' or 'directional'.
        Target sampling rate
    R: float
        Radius of the array sphere, in meter.
    N_order: int
        Maximum spherical harmonic expansion order.
    fs: int
        Sample rate.
    dirCoef: float, optional
        Directivity coefficient of the sensors. Default to None.

    Returns
    -------
    h_mic: ndarray
        Computed IRs in time-domain. Dimension = (N_filt, N_mic, N_doa).
    H_mic: ndarray, dtype='complex'
        Frequency responses of the computed IRs. Dimension = (N_filt//2+1, N_mic, N_doa).

    Raises
    -----
    TypeError, ValueError: if method arguments mismatch in type, dimension or value.

    Notes
    -----
    This method computes the impulse responses of the microphones of a
    spherical microphone array for the given directions of incident plane waves.
    The array type can be either 'open' for omnidirectional microphones in
    an open setup, 'rigid' for omnidirectional microphones mounted on a sphere, or
    'directional' for an open array of first-order directional microphones determined
    by `dirCoef`.
    """

    _validate_int('N_filt', N_filt, positive=True, parity='even')
    _validate_ndarray_2D('mic_dirs_rad', mic_dirs_rad, shape1=masp.utils.C-1)
    _validate_ndarray_2D('src_dirs_rad', src_dirs_rad, shape1=masp.utils.C-1)
    _validate_string('arrayType', arrayType, choices=['open', 'rigid', 'directional'])
    _validate_float('R', R, positive=True)
    _validate_int('N_order', N_order, positive=True)
    _validate_int('fs', fs, positive=True)
    if arrayType is 'directional':
        if dirCoef is None:
            raise ValueError('dirCoef must be defined in the directional case.')
        _validate_float('dirCoef', dirCoef)

    # Compute the frequency-dependent part of the microphone responses (radial dependence)
    f = np.arange(N_filt//2+1) * fs / N_filt
    c = 343.
    kR = 2*np.pi*f*R/c
    b_N = asr.sph_modal_coefs(N_order, kR, arrayType, dirCoef)

    # Handle Nyquist for real impulse response
    temp = b_N.copy()
    temp[-1,:] = np.real(temp[-1,:])
    # Create the symmetric conjugate negative frequency response for a real time-domain signal
    b_Nt = np.real(np.fft.fftshift(np.fft.ifft(np.append(temp, np.conj(temp[-2:0:-1,:]), axis=0), axis=0), axes=0))

    # Compute angular-dependent part of the microphone responses
    # Unit vectors of DOAs and microphones
    N_doa = src_dirs_rad.shape[0]
    N_mic = mic_dirs_rad.shape[0]
    U_doa = masp.utils.sph2cart(src_dirs_rad[:, 0], src_dirs_rad[:, 1], 1)
    U_mic = masp.utils.sph2cart(mic_dirs_rad[:, 0], mic_dirs_rad[:, 1], 1)

    h_mic = np.zeros((N_filt, N_mic, N_doa))
    H_mic = np.zeros((N_filt // 2 + 1, N_mic, N_doa), dtype='complex')

    for i in range(N_doa):
        cosangle = np.dot(U_mic, U_doa[i,:])
        P = np.zeros((N_order + 1, N_mic))
        for n in range(N_order+1):
            for mic in range(N_mic):
                # The Legendre polynomial gives the angular dependency
                Pn = scipy.special.lpmn(n,n,cosangle[mic])[0][0,-1]
                P[n , mic] = (2 * n + 1) / (4 * np.pi) * Pn
        h_mic[:, :, i] = np.matmul(b_Nt, P)
        H_mic[:, :, i] = np.matmul(b_N, P)

    return h_mic, H_mic


def simulate_cyl_array(N_filt, mic_dirs_rad, src_dirs_rad, arrayType, R, N_order, fs):
    """
    Simulate the impulse responses of a cylindrical array.

    Parameters
    ----------
    N_filt : int
        Number of frequencies where to compute the response. It must be even.
    mic_dirs_rad: ndarray
        Directions of microphone capsules, in radians. Dimension = (N_mic).
    src_dirs_rad: ndarray
        Direction of arrival of the indicent plane waves, in radians. Dimension = (N_doa).
    arrayType: str
        'open' or 'rigid'.
        Target sampling rate
    R: float
        Radius of the array cylinder, in meter.
    N_order: int
        Maximum cylindrical harmonic expansion order.
    fs: int
        Sample rate.

    Returns
    -------
    h_mic: ndarray
        Computed IRs in time-domain. Dimension = (N_filt, N_mic, N_doa).
    H_mic: ndarray, dtype='complex'
        Frequency responses of the computed IRs. Dimension = (N_filt//2+1, N_mic, N_doa).

    Raises
    -----
    TypeError, ValueError: if method arguments mismatch in type, dimension or value.

    Notes
    -----
    This method computes the impulse responses of the microphones of a
    cylindrical microphone array for the given directions of incident plane waves.
    The array type can be either 'open' for omnidirectional microphones in
    an open setup, or 'rigid' for omnidirectional microphones mounted on a cylinder.

    """

    _validate_int('N_filt', N_filt, positive=True, parity='even')
    _validate_ndarray_1D('mic_dirs_rad', mic_dirs_rad)
    _validate_ndarray_1D('src_dirs_rad', src_dirs_rad)
    _validate_string('arrayType', arrayType, choices=['open', 'rigid'])
    _validate_float('R', R, positive=True)
    _validate_int('N_order', N_order, positive=True)
    _validate_int('fs', fs, positive=True)

    # Compute the frequency-dependent part of the microphone responses (radial dependence)
    f = np.arange(N_filt//2+1) * fs / N_filt
    c = 343.
    kR = 2*np.pi*f*R/c
    b_N = asr.cyl_modal_coefs(N_order, kR, arrayType)

    # Handle Nyquist for real impulse response
    temp = b_N.copy()
    temp[-1,:] = np.real(temp[-1,:])
    # Create the symmetric conjugate negative frequency response for a real time-domain signal
    b_Nt = np.real(np.fft.fftshift(np.fft.ifft(np.append(temp, np.conj(temp[-2:0:-1,:]), axis=0), axis=0), axes=0))

    # Compute angular-dependent part of the microphone responses
    # Unit vectors of DOAs and microphones
    N_doa = src_dirs_rad.shape[0]
    N_mic = mic_dirs_rad.shape[0]
    h_mic = np.zeros((N_filt, N_mic, N_doa))
    H_mic = np.zeros((N_filt // 2 + 1, N_mic, N_doa), dtype='complex')

    for i in range(N_doa):
        angle = mic_dirs_rad - src_dirs_rad[i]
        C = np.zeros((N_order + 1, N_mic))
        for n in range(N_order+1):
            # Jacobi-Anger expansion
            if n == 0:
                C[n, :] = np.ones(angle.shape)
            else:
                C[n, :] = 2 * np.cos(n*angle)
        h_mic[:, :, i] = np.matmul(b_Nt, C)
        H_mic[:, :, i] = np.matmul(b_N, C)

    return h_mic, H_mic


    # todo lffilt even
def get_array_response(U_doa, R_mic, Lfilt, fs=48000, U_orient=None, fDir_handle=None):
    """
    Return array response of directional sensors.
%
%   GETARRAYRESPONSE computes the impulse responses of the microphones of
%   an open array of directional microphones, located at R_mic and with
%   orientations U_orient, for the directions-of-incidence U_doa. Each
%   sensors directivity in defined by a function handle in the cell array
%   fDir_handle.
%
% U_doa:    Mx3 matrix of vectors specifying the directions to evaluate the
%           impulse response
% R_mic:    Nx3 matrix of vectors specifying the positions of the microphones
% U_orient: Nx3 matrix of unit vectors specifying the orientation of the
%           microphones, or 1x3 unit vector if the microphones all have the
%           same orientation. If left empty or not defined then the
%           orientation of the microphones is assumed to be radial from the
%           origin.
% fDir_hadle:   1xN cell array of function handles describing the directivity
%               of each sensor with respect the sensor's orientation and the
%               DOA. The function considers only axisymmetric directivities,
%               and the function should be of the form f(angle), where
%               angle is the angle between the sensors orientation and the
%               DOA. If a single function handle is provided, the same is
%               applied to all sensors.
% Lfilt:    Length of filter in samples.
% fs:       Sampling rate. If empty or undefined, 48kHz are used.
%
%
% micTFs:   Output the frequency responses for M directions for the N
%           microphones. Only half the FFT spectrum is returned (up to Nyquist).
%           Last dimension is the DOA.
% micIRs:   Output the IRs for M directions for the N microphones. Last
%           dimension is the DOA.
%
%   EXAMPLE - Simulate the response of a 3-microphone array of an
%   omnidirectional microphone, a first-order cardioid and a second-order
%   cardioid, with random locations and orientations, for front and side
%   incidence:
%
%   Nmic = 3;
%   U_doa = [1 0 0; 0 1 0];
%   R_mic = rand(Nmic,3);
%   U_orient = rand(Nmic,3);
%   U_orient = U_orient./(sqrt(sum(U_orient.^2,2))*ones(1,3));   % convert to unit vectors
%
%   fdir_omni = @(angle) ones(size(angle));
%   fdir_card = @(angle) (1/2)*(1 + cos(angle));
%   fdir_card2 = @(angle) (1/2)^2 * (1 + cos(angle)).^2;
%   fDir_handle = {fdir_omni, fdir_card, fdir_card2};
%
%   [micIRs, micTFs] = getArrayResponse(U_doa, R_mic, U_orient, fDir_handle);
%
%   plot(micIRs(:,:,1))
%   legend('omni','1st-order cardioid','2nd-order cardioid')
%
    """

    Nmics = R_mic.shape[0]
    Ndoa = U_doa.shape[0]

    # If no directivity coefficient is defined assume omnidirectional sensors
    if fDir_handle is None:
        # Expand to vector of omni lambdas
        fDir_handle = np.asarray([lambda angle: 1 for i in range(Nmics)])
    else:
        if masp.utils.islambda(fDir_handle):
            fDir_handle = np.asarray([fDir_handle for i in range(Nmics)])
        else:
            _validate_ndarray_1D('fDir_handle', fDir_handle, size=Nmics)
            for i in range(Nmics):
                assert masp.utils.islambda(fDir_handle[i])

    # Compute unit vectors of the microphone positions
    normR_mic = np.sqrt(np.sum(np.power(R_mic, 2), axis=1))
    U_mic = R_mic / normR_mic[:, np.newaxis]

    # If no orientation is defined then assume that the microphones
    # are oriented radially, similar to U_mic
    if U_orient is None:
        U_orient = U_mic
    else:
        _validate_ndarray('U_orient', U_orient)
        if U_orient.ndim == 1:
            _validate_ndarray_1D('U_orient', U_orient, size=masp.utils.C)
            U_orient = np.tile(U_orient, (Nmics, 1))
        else:
            _validate_ndarray_2D('U_orient', U_orient, shape1=masp.utils.C)

    # Frequency vector
    Nfft = Lfilt
    K = Nfft // 2 + 1
    f = np.arange(K) * fs / Nfft

    # Unit vectors pointing to the evaluation points
    U_eval = np.empty((Ndoa, Nmics, masp.utils.C))
    U_eval[:,:,0] = np.tile(U_doa[:, 0], (Nmics, 1)).T
    U_eval[:,:,1] = np.tile(U_doa[:, 1], (Nmics, 1)).T
    U_eval[:,:,2] = np.tile(U_doa[:, 2], (Nmics, 1)).T

    # Computation of time delays and attenuation for each evaluation point to microphone,
    # measured from the origin
    tempR_mic = np.empty((Ndoa, Nmics, masp.utils.C))
    tempR_mic[:,:,0] = np.tile(R_mic[:, 0], (Ndoa, 1))
    tempR_mic[:,:,1] = np.tile(R_mic[:, 1], (Ndoa, 1))
    tempR_mic[:,:,2] = np.tile(R_mic[:, 2], (Ndoa, 1))

    tempU_orient = np.empty((Ndoa, Nmics, masp.utils.C))
    tempU_orient[:,:,0] = np.tile(U_orient[:, 0], (Ndoa, 1))
    tempU_orient[:,:,1] = np.tile(U_orient[:, 1], (Ndoa, 1))
    tempU_orient[:,:,2] = np.tile(U_orient[:, 2], (Ndoa, 1))

    # cos-angles between DOAs and sensor orientations
    cosAngleU = np.sum(U_eval*tempU_orient, axis=2)
    # d*cos-angles between DOAs and sensor positions
    dcosAngleU = np.sum(U_eval*tempR_mic, axis=2)

    # Attenuation due to directionality of the sensors
    B = np.zeros((Ndoa, Nmics))
    for nm in range(Nmics):
        B[:, nm] = fDir_handle[nm](np.arccos(cosAngleU[:, nm]))

    # Create TFs for each microphone
    micTFs = np.zeros((K, Nmics, Ndoa), dtype='complex')
    for kk in range(K):
        omega = 2 * np.pi * f[kk]
        tempTF = B * np.exp(1j * (omega / masp.utils.c) * dcosAngleU)
        micTFs[kk,:,:] = tempTF.T

    # Create IRs for each microphone
    micIRs = np.zeros((Nfft, Nmics, Ndoa))
    for nd in range(Ndoa):
        tempTF = micTFs[:,:, nd].copy()
        tempTF[-1,:] = np.abs(tempTF[-1,:])
        tempTF = np.append(tempTF, np.conj(tempTF[-2:0:-1,:]), axis=0)
        micIRs[:,:, nd] = np.real(np.fft.ifft(tempTF, axis=0))
        micIRs[:,:, nd] = np.fft.fftshift(micIRs[:,:, nd], axes=0)

    return micIRs, micTFs
