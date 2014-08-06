"""
astrom_simple.py

A library containing functions that are useful for solving for the
astrometry of an image

*** NB: Many of these functions are now contained within the Secat class
    that is defined in the catfuncs.py file
****


Generic functions
 read_secat      - reads a catalog, probably generated by SExtractor

"""

import numpy as n
import pyfits as pf
import imfuncs as im
import wcs, coords 
from ccdredux import sigma_clip
from matplotlib import pyplot as plt
from math import pi

#------------------------------------------------------------------------------

def on_click(event):
   print 'button=%d, x=%d, y=%d, xdata=%f, ydata=%f'%(
      event.button, event.x, event.y, event.xdata, event.ydata)

#------------------------------------------------------------------------------

def select_good_ast(astcat, hdr, racol=0, deccol=1, edgedist=50.):
   """
   Creates a mask that identifies the astrometric objects that fall within
   the field of view of the detector.  Returns ra, dec, x, y for the good
   objects

   Inputs:
      astcat   - catalog containing astrometric information
      hdr      - header from the fits file
      racol    - column in astcat containing the RA (zero-indexed)
      deccol   - column in astcat containing the Dec (zero-indexed)
      edgedist - Distance from edge for objects to be considered good
   """

   nx = hdr['naxis1']
   ny = hdr['naxis2']

   mra0,mdec0 = n.loadtxt(astcat,usecols=(racol,deccol),unpack=True)
   mx0,my0 = wcs.sky2pix(hdr,mra0,mdec0)
   goodmask = (mx0>edgedist) & (mx0<nx-edgedist) & \
       (my0>edgedist) & (my0<ny-edgedist)
   mra  = mra0[goodmask]
   mdec = mdec0[goodmask]
   mx   = mx0[goodmask]
   my   = my0[goodmask]
   
   return mra, mdec, mx, my, goodmask

#------------------------------------------------------------------------------

def match_xy(xast, yast, xfits, yfits):
   """
   Finds the closest match, in (x,y) space to each member of the astrometric
   catalog (represented by xast,yast).
   """

   xmin = 0.*xast
   ymin = 0.*yast

   for i in range(xast.size):
      dx = xast[i] - xfits
      dy = yast[i] - yfits
      dpos = dx**2 + dy**2
      sindex = n.argsort(dpos)
      xmin[i] = xfits[sindex[0]]
      ymin[i] = yfits[sindex[0]]

   return xmin,ymin

#------------------------------------------------------------------------------

def calc_offsets(astcat, hdr, xfits, yfits, maxoffset=None, doplot=True,
                 racol=0, deccol=1, edgedist=50.):
   """
   Calculates the (x,y) offsets between the astrometric catalog and the
   catalog derived from the fits image.  The astrometric catalog (x,y) positions
   are derived from the (RA,Dec) values in the catalog, mapped to (x,y) using
   the fits header (hdr).

   """

   """
   Select the astrometric catalog objects that fall within the fits file FOV
   (at least with its current WCS)
   """
   raa,deca,xa,ya,astmask = select_good_ast(astcat,hdr,racol,deccol,edgedist)

   """
   Find the closest match to each astrometric catalog object and calculate the
   offsets.
   """
   xm,ym = match_xy(xa,ya,xfits,yfits)
   dx = xa - xm
   dy = ya - ym
   if maxoffset is not None:
      dpos = n.sqrt(dx**2 + dy**2)
      goodmask = dpos<maxoffset
   else:
      goodmask = n.ones(xast.size,dtype=bool)
   dxm = dx[goodmask]
   dym = dy[goodmask]
   

   """
   Plot the offsets if desired
   """
   if doplot:
      plt.figure()
      plt.scatter(dxm,dym)
      plt.xlabel('x offset (pix)')
      plt.ylabel('y offset (pix)')
      plt.axhline(color='k')
      plt.axvline(color='k')
      plt.axhline(n.median(dxm),color='r')
      plt.axvline(n.median(dym),color='r')
      plt.show()

   """
   Return the offsets
   """
   return dxm,dym

#------------------------------------------------------------------------------

def match_fits_to_ast(fitsfile, fitscat, astcat, outfile=None, max_offset=None, 
                      racol=1, deccol=2, xcol_fits=8, ycol_fits=9, 
                      doplot=True, edgedist=50., imhdu=0, verbose=True):

   """
   Given a fits file, its associated catalog, and an astrometric catalog,
   find the closest matches of the astrometric objects to those contained
   in the catalog derived from the fits file, using the WCS information
   in the fits header.
   """

   if(verbose):
      print "Running match_fits_to_ast with:"
      print "   fitsfile = %s" % fitsfile
      print "   fitscat  = %s" % fitscat
      print "   astcat   = %s" % astcat

   """
   Start by opening the fits file and reading the appropriate columns from
   the catalogs
   """
   hdulist = im.open_fits(fitsfile)
   if verbose:
      print ""
   hdulist.info()
   hdr         = hdulist[imhdu].header
   xfits,yfits = n.loadtxt(fitscat,unpack=True,usecols=(xcol_fits,ycol_fits))
   """
   Select the astrometric catalog objects that fall within the fits file FOV
   (at least with its current WCS)
   """
   raa,deca,xa,ya,astmask = select_good_ast(astcat,hdr,racol,deccol,edgedist)

   """
   Find the closest match to each astrometric catalog object and calculate the
   offsets.
   Do two loops, to deal with possible confusion of sources on first pass
   through
   """
   dxmed = 0
   dymed = 0
   for i in range(2):
      if verbose:
         print ''
         print 'Pass %d' % (i+1)
         print '------------------------'
      xa0 = xa - dxmed
      ya0 = ya - dymed
      xm0,ym0 = match_xy(xa0,ya0,xfits,yfits)
      if verbose:
         print 'Found %d matched objects' % xm0.size
      dx = xa - xm0
      dy = ya - ym0
      dxmed = n.median(dx)
      dymed = n.median(dy)
      if max_offset is not None:
         dpos = n.sqrt(dx**2 + dy**2)
         goodmask = dpos<max_offset
         if verbose:
            print "Applying a maximum offset cut of %7.1f pixels" % max_offset
            print "Median shifts before clipping: %7.2f %7.2f" % (dxmed,dymed)
      else:
         goodmask = n.ones(xa.size,dtype=bool)
      dxm  = dx[goodmask]
      dym  = dy[goodmask]
      xm   = xm0[goodmask]
      ym   = ym0[goodmask]
      ram  = raa[goodmask]
      decm = deca[goodmask]
      dxmed = n.median(dxm)
      dymed = n.median(dym)
      if verbose:
         print "Median shifts after pass:   %7.2f %7.2f" % (dxmed,dymed)

   """
   Plot the offsets if desired
   """
   if doplot:
      dxmed = n.median(dxm)
      dymed = n.median(dym)
      plt.figure()
      plt.scatter(dxm,dym)
      plt.xlabel('x offset (pix)')
      plt.ylabel('y offset (pix)')
      plt.axhline(color='k')
      plt.axvline(color='k')
      plt.axvline(n.median(dxm),color='r')
      plt.axhline(n.median(dym),color='r')
      print ""
      print "Black lines represent x=0 and y=0 axes"
      print "Red lines show median offsets of dx_med=%7.2f and dy_med=%7.2f" \
          % (dxmed,dymed)
      #plt.show()

   if outfile is not None:
      if verbose:
         print ""
         print "Printing to output file %s" % outfile
         print ""
      f = open(outfile,'w')
      f.write('# (x,y) catalog: %s\n' % fitscat)
      f.write('# Astrometric catalog: %s\n' % astcat)
      f.write('# Columns are x y RA Dec\n')
      for i in range(xm.size):
         f.write('%8.2f %8.2f  %11.7f %+11.7f\n' % (xm[i],ym[i],ram[i],decm[i]))
      f.close()
      return
   else:
      return ram,decm,xm,ym,dxm,dym,astmask,goodmask

#------------------------------------------------------------------------------

def rscale_ccmap(ccmap_in, database, images, xcol=1, ycol=2, racol=3, deccol=4,
                 lngunits='degrees', latunits='degrees', interactive=True):
   """
   Uses the pyraf ccmap task to update the WCS
   """

   from pyraf import iraf

   iraf.ccmap(ccmap_in,database,images=images,xcolumn=xcol,ycolumn=ycol,
              lngcolumn=racol,latcolumn=deccol,lngunits=lngunits,
              latunits=latunits,insystem='j2000',fitgeometry='rscale',
              maxiter=1,reject=2.5,update=True,interactive=interactive)

#------------------------------------------------------------------------------

def fit_trans(update_wcs, fitsfile, fitscat, astcat, racol_ast=1, deccol_ast=2,
              xcol_fits=8, ycol_fits=9, max_offset=None, doplot=True,
              edgedist=50., imhdu=0):
   """
   Solves for the astrometry by fitting for a simple translation between
   the fits file coordinates and the astrometric catalog
   """

   """
   Start by opening the fits file and reading the appropriate columns from
   the catalogs
   """
   if update_wcs:
      hdulist = im.open_fits(fitsfile,'update')
   else:
      hdulist = im.open_fits(fitsfile)
   print ""
   hdulist.info()
   hdr         = hdulist[imhdu].header
   xfits,yfits = n.loadtxt(fitscat,unpack=True,usecols=(xcol_fits,ycol_fits))

   """
   Calculate the offsets
   """
   dx,dy = calc_offsets(astcat,hdr,xfits,yfits,max_offset,doplot,racol_ast,
                        deccol_ast,edgedist)
   dx_crpix = n.median(dx)
   dy_crpix = n.median(dy)
   print ""
   print "Median offsets are: %+7.2f %+7.2f" % (dx_crpix,dy_crpix)

   """
   Apply the correction to the WCS, for now only in memory
   """
   print "Applying median offsets to the WCS CRPIX values"
   hdr['crpix1'] -= dx_crpix
   hdr['crpix2'] -= dy_crpix

   """
   Plot the offsets after the correction, if desired
   """
   if doplot:
      dx,dy = calc_offsets(astcat,hdr,xfits,yfits,max_offset,doplot,racol_ast,
                           deccol_ast,edgedist)

   """
   Save the corrected WCS if requested
   """
   if update_wcs:
      hdulist.flush()
   else:
      hdulist.close()

#------------------------------------------------------------------------------

def plot_astcat(infile, astcat, rmarker=10., racol=0, deccol=1, hext=0):

   # Turn on interactive, so that plot occurs first and then query
   plt.ion()

   """ Load fits file """
   fitsim = im.Image(infile)
   hdr = fitsim.hdulist[hext].header

   """ Select astrometric objects within the FOV of the detector """
   mra,mdec,mx,my,astmask = select_good_ast(astcat,hdr,racol,deccol)

   """ Plot the fits file and mark the astrometric objects """
   fig = plt.figure(1)
   fitsim.display(cmap='heat')
   plt.plot(mx,my,'o',ms=rmarker,mec='g',mfc='none',mew=2)
   plt.xlim(0,nx)
   plt.ylim(0,ny)

   plt.draw()
   #cid = fig.canvas.mpl_connect('button_press_event', on_click)

   """ 
   Be careful of the +1 offset between SExtractor pixels and python indices
   """

   return fitsim


#------------------------------------------------------------------------------

def init_shifts(fitsim, astcat, xycat, rmarker=10., racol=0, deccol=1, 
                xcol=6, ycol=7, hext=0):
   """
   The user selects a pair of objects, one from the astrometric catalog
   (green circles plotted in plot_astcat) and one from the fits image.
   The pixel offset between the two is calculated, converted into arcsec,
   and then applied to the crval header cards in the input fits image.
   """

   """ Read x and y positions for sources in input catalog """
   xfits,yfits = n.loadtxt(xycat,usecols=(xcol,ycol),unpack=True)

   """ Get WCS information from input fits file """
   hdr = fitsim.hdulist[hext].header.copy()
   wcsinfo = wcs.parse_header(hdr)
   cdelt1,cdelt2,crota1,crota2 = coords.cdmatrix_to_rscale(wcsinfo[2])
   print ""
   print "Current parameters of image"
   print "---------------------------"
   print " Pixel scales (arcsec/pix): %6.3f %6.3f" % (-cdelt1*3600.,cdelt2*3600.)
   print " Image rotation (deg N->E): %+7.2f" % (crota2 * 180./pi)

   """ Select astrometric objects within the FOV of the detector """
   mra,mdec,mx,my,astmask = select_good_ast(astcat,hdr,racol,deccol)

   """ Select astrometric object used to determine the shift """
   print ""
   print "Determining initial shifts"
   print "----------------------------------------------------------"
   print "Choose a green circle that can clearly matched to an object in the"
   print " image."
   foo = raw_input(
       'Enter position for the chosen circle (just need to be close) [x y]: ')
   while len(foo.split()) != 2:
      print "ERROR.  Need to enter as two space-separated numbers."
      foo = raw_input('Enter position again: ')
   xast0,yast0 = foo.split()
   dist = n.sqrt((mx - float(xast0))**2 + (my - float(yast0))**2)
   astind = n.argsort(dist)[0]
   print "Closest match in astrometric catalog found at %8.2f %8.2f" % \
       (mx[astind],my[astind])

   """ Select the matching object in the xy catalog """
   print ""
   print "Now hoose the matching object seen in the fits image."
   foo = raw_input(
       'Enter position for the chosen object (just need to be close) [x y]: ')
   while len(foo.split()) != 2:
      print "ERROR.  Need to enter as two space-separated numbers."
      foo = raw_input('Enter position again: ')
   xcat0,ycat0 = foo.split()
   dist = n.sqrt((xfits - float(xcat0))**2 + (yfits - float(ycat0))**2)
   catind = n.argsort(dist)[0]
   print "Closest match in image catalog found at %8.2f %8.2f" % \
       (xfits[catind],yfits[catind])

   """ Calculate the offets in arcsec """
   dxpix = xfits[catind] - mx[astind]
   dypix = yfits[catind] - my[astind]
   da = dxpix * cdelt1
   dd = dypix * cdelt2
   print ""
   print "Calculated Offsets (image - astrometric)"
   print "----------------------------------------"
   print "x:  %+7.2f pix  %+7.2f arcsec" % (dxpix,da*3600.)
   print "y:  %+7.2f pix  %+7.2f arcsec" % (dypix,dd*3600.)


   #fig = plt.figure(1)
   #cid = fig.canvas.mpl_connect('button_press_event', on_click)
   
   #print "Done with that"
   #fig.canvas.mpl_disconnect(cid)
